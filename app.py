"""app.py

Example NLP tool wrapper where the tool is a very simplistic tokenizer.

"""

import os
import json
import collections

# Imports needed for CLAMS and MMIF. Note that non-NLP CLAMS applications also
# import AnnotationTypes from mmif.vocabulary, but this is not needed for NLP
# applications.
from clams.serve import ClamsApp
from clams.restify import Restifier
from mmif.serialize import *
from mmif.vocabulary import DocumentTypes

# For an NLP tool we need to import the LAPPS vocabulary items
# At some point those items may be made available in the mmif package.
from lapps.discriminators import Uri

# Import the NLP tool. The NLP tool code may also be embedded in this script.
import tokenizer

# We use this to find the text documents in the documents list
TEXT_DOCUMENT = os.path.basename(DocumentTypes.TextDocument.value)


class TokenizerApp(ClamsApp):

    def setupmetadata(self):
        return {
            "name": "Tokenizer Wrapper",
            "app": 'https://apps.clams.ai/tokenizer',
            "app_version": "0.0.2",
            "tool_version": "0.1.0",
            "mmif-spec-version": "0.2.1",
            "mmif-sdk-version": "0.2.0",
            "clams-version": "0.1.3",
            "description": "This tool applies simple tokenization to all text documents in an MMIF file.",
            "vendor": "Team CLAMS",
            "requires": [DocumentTypes.TextDocument.value],
            "produces": [Uri.TOKEN]
        }

    def sniff(self, mmif):
        # this mock-up method always returns true
        return True

    def annotate(self, mmif):
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
        return self.mmif.serialize(pretty=True)

    def _new_view(self, docid=None):
        view = self.mmif.new_view()
        view.metadata.app = self.metadata['app']
        properties = {} if docid is None else {'document': docid}
        view.new_contain(Uri.TOKEN, properties)
        return view

    def _read_text(self, textdoc):
        """Read the text content from the document or the text value."""
        if textdoc.location:
            with open(textdoc.location) as fh:
                text = fh.read()
        else:
            text = textdoc.properties.text.value
        return text

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


def text_documents(documents):
    """Utility method to get all text documents from a list of documents."""
    return [doc for doc in documents if doc.at_type.endswith(TEXT_DOCUMENT)]


class Identifiers(object):

    """Utility class to generate annotation identifiers. You could, but don't have
    to, reset this each time you start a new view. This works only for new views
    since it does not check for identifiers of annotations already in the list
    of annotations."""

    identifiers = collections.defaultdict(int)

    @classmethod
    def new(cls, prefix):
        cls.identifiers[prefix] += 1
        return "%s%d" % (prefix, cls.identifiers[prefix])

    @classmethod
    def reset(cls):
        cls.identifiers = collections.defaultdict(int)


if __name__ == "__main__":

    app = TokenizerApp()
    service = Restifier(app)
    service.run()
