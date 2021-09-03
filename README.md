# Wrapping an NLP Application

This repository is a tutorial on how to wrap a simple NLP tool as a CLAMS application. This may not make a lot of sense without glancing over recent MMIF specifications at [https://mmif.clams.ai/](https://mmif.clams.ai/). The example in here is for CLAMS version 0.5.0 from July 2021.

When building this application you need Python 3.6 or higher and install some modules, preferably in a clean Python virtual environment:

```
$ pip install clams-python==0.5.0
```

This installs the CLAMS Python interface, which in turn installs the Python interface to the MMIF format and some third party modules like Flask. It also installs the LAPPS Python interface, which is relevant to most NLP applications.

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

By convention, all the wrapping code is in a script named `app.py`, but this is not a strict requirement and you can give it another name. The `app.py` script does several things: (1) import the necessary code, (2) create a subclass of `ClamsApp` that defines the metadata and provides a method to run the wrapped NLP tool, and (3) provide a way to run the code as a RESTful Flask service. The most salient parts of the code are explained here.

**Imports**

Aside from a few standard modules we need the following imports:

```python
from clams.app import ClamsApp
from clams.restify import Restifier
from clams.appmetadata import AppMetadata
from mmif.serialize import Mmif
from mmif.vocabulary import DocumentTypes
from lapps.discriminators import Uri
import tokenizer
```

For non-NLP CLAMS applications we would also do  `from mmif.vocabulary import AnnotationTypes`, but this is not needed for NLP applications because they do not need the CLAMS vocabulary. What we do need to import are the URIs of all LAPPS annotation types and the NLP tool itself. 

Importing `lapps.discriminators.Uri` is for convenience since it gives us easy acces to the URIs of annotation types and some of their attributes. The following code prints a list of available variables that point to URIs:

```python
>>> from lapps.discriminators import Uri
>>> attrs = [x for x in dir(Uri) if not x.startswith('__')]
>>> attrs = [a for a in attrs if not getattr(Uri, a).find('org/ns') > -1]
>>> print(' '.join(attrs))
ANNOTATION CHUNK CONSTITUENT COREF DATE DEPENDENCY DEPENDENCY_STRUCTURE DOCUMENT GENERIC_RELATION LEMMA LOCATION LOOKUP MARKABLE MATCHES NCHUNK NE ORGANIZATION PARAGRAPH PERSON PHRASE_STRUCTURE POS RELATION SEMANTIC_ROLE SENTENCE TOKEN VCHUNK
```

**The application class**

With the imports in place we define a subclass of `ClamsApp` which needs two methods:

```python
class TokenizerApp(ClamsApp):
    def _appmetadata(self): pass
    def _annotate(self, mmif): pass
```

Here it is useful to introduce some background. The CLAMS RESTful API connects the GET and POST methods to the `appmetdata()`  and  `annotate()` methods on the app. These methods do not need to be defined here because they are defined on `ClamsApp`. In essence, those two methods are wrappers around  `_appmetadata()` and   `_annotate()` and provide some common functionality like making sure the output is serialized into a string.

The `_appmetadata()` method defines the metadata for the app:

```python
def _appmetadata(self):
    metadata = AppMetadata(
        identifier='https://apps.clams.ai/tokenizer',
        url='https://github.com/clamsproject/app-nlp-example',
        name="Simplistic Tokenizer",
        description="Apply simple tokenization to all text documents in an MMIF file.",
        app_version=APP_VERSION,
        app_license=APP_LICENSE,
        analyzer_version=TOKENIZER_VERSION,
        analyzer_license=TOKENIZER_LICENSE,
        mmif_version=MMIF_VERSION
    )
    metadata.add_input(DocumentTypes.TextDocument)
    metadata.add_output(Uri.TOKEN)
    return metadata
```

The variables used in the code above are defined closer to the top of the file:

```python
APP_VERSION = '0.0.5'
APP_LICENSE = 'Apache 2.0'
MMIF_VERSION = '0.4.0'
MMIF_PYTHON_VERSION = '0.4.5'
CLAMS_PYTHON_VERSION = '0.5.0'
TOKENIZER_VERSION = '3.0.3'
TOKENIZER_LICENSE = 'Apache 2.0'
```

The MMIF_PYTHON_VERSION and CLAMS_PYTHON_VERSION variables are technically not needed since they are implied by using `pip install clams-python==0.5.0`, but I find it helpful to name them explicitly.

The `_annotate()` method always returns an MMIF object and it is where most of the work starts. For a text processing app, it is mostly concerned with finding text documents, creating new views and calling the code that runs over the text and inserts the results.

```python
def _annotate(self, mmif, **kwargs):
    # reset identifier counts for each annotation
    Identifiers.reset()
    # Initialize the MMIF object from he string if needed
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
    # return the MMIF object
    return self.mmif
```

For language processing applications, one task is to retrieve all text documents from both the documents list and the views. Annotations generated by the NLP tool need to be anchored to the text documents, which in the case of text documents in the documents list is done by using the text document identifier, but for text documents in views we also need the view identifier. A view may have many text documents and typically all annotations created will be put in one view.

For each text document from the document list, there is one invocation of `_new_view()` which gets handed a document identifier so it can be put in the view metadata. And for each view with text documents there is also one invocation of `_new_view()`, but no document identifier is handed in so the identifier will not be put into the view metadata.

The method  `_run_nlp_tool()` is responsible for running the NLP tool and adding annotations to the new view. The third argument allows us to anchor annotations created by the tool by handing over the document identifier, possibly prefixed by the view the document lives in.

One thing about `_annotate()` as it is defined above is that it will most likely be the same for each NLP application, all the application specific details are in the code that creates new views and the code that adds annotations.

Creating a new view:

```python
def _new_view(self, docid=None):
    view = self.mmif.new_view()
    view.metadata.app = self.metadata.identifier
    view.new_contain(Uri.TOKEN, document=docid)
    return view
```

This is the simplest NLP view possible since there is only one annotation type and it has no metadata properties beyond the `document` property. Other applications may have more annotation types, which results in repeated invocations of `new_contain()`, and may define other metadata properties for those types.

Adding annotations:

```python
def _run_nlp_tool(self, doc, new_view, full_doc_id):
    """Run the NLP tool over the document and add annotations to the view, using the
    full document identifier (which may include a view identifier) for the document
    property."""
    text = self._read_text(doc)
    tokens = tokenizer.tokenize(text)
    for p1, p2 in tokens:
        a = new_view.new_annotation(Uri.TOKEN, Identifiers.new("t"))
        # no need to do this for documents in the documents list
        if ':' in full_doc_id:
            a.add_property('document', full_doc_id)
        a.add_property('start', p1)
        a.add_property('end', p2)
        a.add_property('text', text[p1:p2])
```

First, with `_read_text()` we get the text from the text document, either from its `location` property or from its `text`property. Second, we apply the tokenizer to the text. And third, we loop over the token offsets in the tokenizer result and create annotations of type `Uri.TOKEN` with an identfier that is generated using the `Identifiers` class. All that is needed for adding an annotation is the `add_annotation()` method on the view object and the `add_property()` method on the annotation object.

**Running a server**

Finally, the last three lines of `app.py` will run the tokenizer wrapper as a Flask service:


```python
app = TokenizerApp()
service = Restifier(app)
service.run()
```

This is for a development server, in case you want to start a production server use `serve_production()` instead of `run()`.

### 3.  Testing the application

There are two ways to test the application. The first is to use the `test.py` script, which will just test the wrapping code without using Flask:

```
$ python test.py example-mmif.json out.json
```

When you run this the `out.json` file should be about 10K in size and contain pretty printed JSON. And at the same time something like the following should be printed to the standard output:

```
<View id=v_1 annotations=2 app=http://mmif.clams.ai/apps/east/0.2.1>
<View id=v_2 annotations=4 app=http://mmif.clams.ai/apps/tesseract/0.2.1>
<View id=v_3 annotations=24 app=https://apps.clams.ai/tokenizer>
<View id=v_4 annotations=6 app=https://apps.clams.ai/tokenizer>
```

The second way tests the behavior of the application in a Flask server by running the application as a service in one terminal:

```
$> python app.py
```

And poking at it from another:

```
$ curl http://0.0.0.0:5000/
$ curl -H "Accept: application/json" -X POST -d@example-mmif.json http://0.0.0.0:5000/
```

The first one prints the metadata and the second the output MMIF file. Appending `?pretty=True` to the last URL will result in pretty printed output.

One note on the example input MMIF file is that it has two documents, a video document and a text document. The text document has the text inline in a text value field. You could also give it a location as follows

```json
{
  "@type": "http://mmif.clams.ai/0.3.1/vocabulary/VideoDocument",
  "properties": {
    "id": "m1",
    "mime": "text/plain",
    "location": "/var/archive/text/example-transcript.mp4"
}
```

The location has to be URL or an absolute path and it is your resonsibility to make sure it exists. Note how the video document in the example does define a path which most likely does not exist. This is not hurting us because at no time are we accessing that location.



### 4.  Configuration files and Docker

Apps within CLAMS typically run as Docker containers and after an app is tested as a local Flask application it should be dockerized. Three configuration files for building a Docker image are part of this example repository:

| file             | description                                                  |
| ---------------- | :----------------------------------------------------------- |
| Dockerfile       | Describes how to create a Docker image for this application. |
| .dockerignore    | Specifies which files are not needed for running this application. |
| requirements.txt | File with all Python modules that need to be installed.      |

Here is the minimal Dockerfile included with this example:

```dockerfile
FROM python:3.6-slim-buster
WORKDIR ./app
COPY ./requirements.txt .
RUN pip3 install -r requirements.txt
COPY ./ ./
CMD ["python3", "app.py"]
```

This starts from the official `python:3.6-slim-buster` image and installs the requirements ( the `clams-python` package and the code it depends on). The Dockerfile only needs to be edited if additional installations are required to run the NLP tool, for extra Python modules you would typically only change the requirements file. This repository also includes a  `.dockerignore`  file. Editing it is optional, but with large repositories with lots of documentation and images you may want to add some file paths just to keep the image as small as possible.

To build the Docker image you do the following, where the -t option let's you pick a name for the image, you can use another name if you like:

```
$ docker build -t clams-nlp-example .
```

To test the Flask app in the container do

```
$ docker run --rm -it clams-nlp-example bash
```

You are now running a bash shell in the container (escape out with Ctrl-d) and in the container you can run

```
root@c85a08b22f18:/app# python3 test.py example-mmif.json out.json 
```

To test the Flask app in the container do

```
$ docker run --name clams-nlp-example --rm -d -p 5000:5000 clams-nlp-example
```

The `--name` option gives a name to the container which we use later to stop it (if we do not name the container then Docker will generate a name and we have to query docker to see what containers are running and then use that name to stop it). Now you can use curl to send requests:

```
$ curl http://0.0.0.0:5000/
$ curl -H "Accept: application/json" -X POST -d@example-mmif.json http://0.0.0.0:5000/
```


