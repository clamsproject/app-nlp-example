# Wrapping an NLP Application

This repository is a tutorial on how to wrap a simple NLP tool as a CLAMS application. This may not make a lot of sense without glancing over recent MMIF specifications at [https://mmif.clams.ai/](https://mmif.clams.ai/).

### 1.  The NLP tool

We use a simple tokenizer in `tokenizer.py` as the example NLP tool. All it does is to define a tokenize function that uses a simple regular expression and returns a list of offset pairs.

```python {.line-numbers}
def tokenize(text):
    return [tok.span() for tok in re.finditer("\w+", text)]
```

```python
>>> import tokenizer
>>> tokenizer.tokenize('Fido barks.')
[(0, 4), (5, 10)] 
```

### 2.  Wrapping the tokenizer

By convention, all the wrapping code is in a script named `app.py`. It does several things: (1) it imports the necessary code, (2) it creates a subclass of `ClamsApp` that defines the metadata and provides a method to run the wrapped NLP tool, and (3) it provides a way to run the code as a RESTFul Flask service. The most salient parts of the code are explained here.

Aside from a few standard modules we need the following imports:

```python
from clams.serve import ClamsApp
from clams.restify import Restifier
from mmif.serialize import *
from mmif.vocabulary import DocumentTypes
from lapps.discriminators import Uri
import tokenizer
```

The third line imports some classes needed to create MMIF files:

```python
>>> import mmif
>>> mmif.serialize.__all__
['Annotation', 'AnnotationProperties', 'Document', 'DocumentProperties', 'Text', 'Mmif', 'View', 'ViewMetadata', 'Contain']
```

For non-NLP CLAMS applications we also import `AnnotationTypes` from `mmif.vocabulary`, but this is not needed for NLP applications because they do not need the CLAMS vocabulary. What we do need to import are the URIs of all LAPPS annotation types and the NLP tool itself. 

```python
>>> from lapps.discriminators import Uri
>>> attrs = [x for x in dir(Uri) if not x.startswith('__')]
>>> attrs = [a for a in attrs if not getattr(Uri, a).find('org/ns') > -1]
>>> print(' '.join(attrs))
ANNOTATION CHUNK CONSTITUENT COREF DATE DEPENDENCY DEPENDENCY_STRUCTURE DOCUMENT GENERIC_RELATION LEMMA LOCATION LOOKUP MARKABLE MATCHES NCHUNK NE ORGANIZATION PARAGRAPH PERSON PHRASE_STRUCTURE POS RELATION SEMANTIC_ROLE SENTENCE TOKEN VCHUNK
```

Importing `lapps.discriminators.Uri` is for convenience since it gives us easy acces to the URIs of annotation types and some of their attributes. The following code prints a list of available variables that point to URIs:

```python
>>> from lapps.discriminators import Uri
>>> attrs = [x for x in dir(Uri) if not x.startswith('__')]
>>> attrs = [a for a in attrs if not getattr(Uri, a).find('org/ns') > -1]
>>> print(' '.join(attrs))
ANNOTATION CHUNK CONSTITUENT COREF DATE DEPENDENCY DEPENDENCY_STRUCTURE DOCUMENT GENERIC_RELATION LEMMA LOCATION LOOKUP MARKABLE MATCHES NCHUNK NE ORGANIZATION PARAGRAPH PERSON PHRASE_STRUCTURE POS RELATION SEMANTIC_ROLE SENTENCE TOKEN VCHUNK
```

With the imports in place we define a subclass of `ClamsApp` which needs three public methods:

```python
class TokenizerApp(ClamsApp):
    def setupmetadata(self): pass
    def sniff(self, mmif): pass
    def annotate(self, mmif): pass
```

The `setupmetadata()` method defines the metadata for the app:

```python
def __init__(self):
    return {
      "name": "Tokenizer Wrapper",
      "app": 'https://apps.clams.ai/tokenizer',
      "app_version": "0.0.2",
      "tool_version": "0.1.0",
      "mmif-spec-version": "0.2.1",
      "mmif-sdk-version": "0.2.0",
      "clams-version": "0.1.3",
      "description": "Applies simple tokenization to all text documents in an MMIF file.",
      "vendor": "Team CLAMS",
      "requires": [DocumentTypes.TextDocument.value],
      "produces": [Uri.TOKEN]
    }
```

At the moment, this is mostly inconsequential because the CLAMS platform does not yet use these metadata, but at some point they will be used to generate an entry in the CLAMS tool shed. There are no strict rules yet on what should be in the metadata and the above is a guesstimate. The only metadata property that is being used is the `app` property, which is added to the view metadata.

The `sniff()` method should return True if the input meets the requirements of the application. For now, we do not do any checking and assume useful input.

The `annotate()` method is where most of the work starts. It is mostly concerned with finding text documents, creating new views and calling the code that runs over the text and inserts the results.

```python
def annotate(self, mmif):
    # reset identifier counts for each annotation
    Identifiers.reset()
    self.mmif = mmif if type(mmif) is Mmif else Mmif(mmif)
    # process the text documents in the documents list
    for doc in text_documents(self.mmif.documents):
        new_view = self._new_view(doc.id)
        self._run_nlp_tool(doc, new_view, doc.id)
    # process the text documents in all the views, we copy the views into a
    # list because self.mmif.views will be changed
    for view in list(self.mmif.views):
        docs = self.mmif.get_documents_in_view(view.id)
        if docs:
            new_view = self._new_view()
                for doc in docs:
                    doc_id = view.id + ':' + doc.id
                    self._run_nlp_tool(doc, new_view, doc_id)
    return self.mmif
```

For language processing applications, one task is to retrieve all text documents from both the documents list and the annotations in all views. Moreover, annotations generated by the NLP tool need to be anchored to those documents, which in the case of text documents in the documents list could simply be to the text document identifier, but which the case of text documents in views also needs to view identifier. Also note that a view may have many text documents and all annotations created will be put in one view. This has two consequences:

1.  For a document from the document list, there is one invocation of `_new_view()` which gets handed a document identifier so it can be put in the view metadata, and there is one invocation of `_new_view()` for views with text documents, but the document identifier is not handed in so the identefier will not be put into the view metadata.
2. The method  `_run_nlp_tool()` is responsible for running the NLP tool and adding annotations to the new view. The third argument allows us to anchor annotations created by the tool by handing over the document identifier, possibly prefixed by the view the document lives in.

One thing about `annotate()` is that most likely it will be the same for each NLP application, all the application specific details are in the code that creates new views and the code that adds annotations.

Creating a new view:

```python
def _new_view(self, docid=None):
    view = self.mmif.new_view()
    view.metadata.app = self.metadata['app']
    properties = {} if docid is None else {'document': docid}
    view.new_contain(Uri.TOKEN, properties)
    return view
```

This is the simplest NLP view possible since there is only one annotation type and it has no metadata properties beyond the `document` property. Other applications may have more annotation types, which results in repeated invocations of `new_contain()`, and may define metadata properties for those types. Property dictionaries should be created from scratch for each annotation type.

Adding annotations:

```python
def _run_nlp_tool(self, doc, new_view, full_doc_id):
    """Run the NLP tool over the document and add annotations to the view, using the
    full document identifier (which may include a view identifier) for the document
    property."""
    text = self._read_text(doc)
    tokens = tokenizer.tokenize(text)
    for p1, p2 in tokens:
        a = new_view.new_annotation(Identifiers.new("t"), Uri.TOKEN)
        # no need to do this for documents in the documents list
        if ':' in full_doc_id:
            a.add_property('document', full_doc_id)
        a.add_property('start', p1)
        a.add_property('end', p2)
        a.add_property('text', text[p1:p2])
```

First, with `_read_text()` we get the text from the text document, either from its `location` property or from its `text`property. Second, we apply the tokenizer to the text. And third, we loop over the token offsets in the tokenizer result and create annotations of type `Uri.TOKEN` with an identfier that is generated using the `Identifiers` class. All that is needed for adding an annotation is the `add_annotation()` on the view object and the `add_property()` method on the annotation object.

Finally, the last three lines of `app.py` will run the tokenizer wrapper as a Flask service:


```python
app = TokenizerApp()
service = Restifier(app)
service.run()
```

### 3.  Testing the application

There are two simple ways to test the application. One is to use the `test.py` script, which will just test the wrapping code without using Flask:

```bash
$ python test.py example-mmif.json out.json
```

The second way tests the behavior of the applicaiton in a Flask server by running the application as a service in one terminal:

```bash
$ python app.py
```

And poking at it from another:

```bash
$ curl -i -H "Accept: application/json" -X PUT -d@example-mmif.json http://0.0.0.0:5000/
```

### 4.  Configuration files and Docker

Three configuration files are part of this example repository:

| file             | description                                                  |
| ---------------- | :----------------------------------------------------------- |
| Dockerfile       | Describes how to create a Docker image for this applicaiton. |
| requirements.txt | File with all Python packages to be loaded.                  |
| config.xml       | Configuration file for Galaxy.                               |

The docker file only needs to be edited if additional installations are required to run the NLP tool. The same holds for the requirements file, the version in this repository only requires the packages needed for CLAMS and MMIF, which take care of dependencies like loading the Flask packages. For the Galaxy configuration file, all that needs to be edited are the first line and the label of the output.

Here is the minimal Dockerfile included with this example:

```dockerfile
FROM python:3.6-buster
COPY ./ ./app
WORKDIR ./app
RUN pip3 install -r requirements.txt
CMD python app.py
```

The Python image used is somewhat of an overkill for the simple tokenizer we are using in this example.

To build the Docker image you do:

```bash
$ docker build -t clams-tokenizer-app .
```

To test the Flask app in the container do

```bash
$ docker run --rm -it clams-tokenizer-app bash
```

And in the container you can run

```bash
$ python3 test.py example-mmif.json out.json 
```

To test the Flask app in the container do

```bash
$ docker run --rm -p 5000:5000 clams-tokenizer-app
```

And now you can use curl to send requests:

```bash
$ curl -i -H "Accept: application/json" -X GET http://0.0.0.0:5000/
$ curl -i -H "Accept: application/json" -X PUT -d@example-mmif.json http://0.0.0.0:5000/
```

