"""app.py

Example NLP tool wrapper where the tool is a very simplistic tokenizer.

"""

import os
import json
import urllib
import argparse
import collections

# Imports needed for CLAMS and MMIF. Note that non-NLP CLAMS applications also
# import AnnotationTypes from mmif.vocabulary, but this is not needed for NLP
# applications.
from clams.app import ClamsApp
from clams.restify import Restifier
from clams.appmetadata import AppMetadata
from mmif.serialize import Mmif
from mmif.vocabulary import DocumentTypes

# For an NLP tool we need to import the LAPPS vocabulary items
# At some point those items may be made available in the mmif package.
from lapps.discriminators import Uri

# Import the NLP tool. The NLP tool code may also be embedded in this script.
import tokenizer

# Making version dependencies explicit. Some, but not yet all, of these are
# added to the metadata of the application.
VERSION = '0.0.5'
MMIF_VERSION = '0.4.0'
MMIF_PYTHON_VERSION = '0.4.5'
CLAMS_PYTHON_VERSION = '0.4.4'
TOKENIZER_VERSION = tokenizer.__VERSION__

# We use this to find the text documents in the documents list
TEXT_DOCUMENT = os.path.basename(str(DocumentTypes.TextDocument))


APP_VERSION = '0.0.5'
APP_LICENSE = 'Apache 2.0'
MMIF_VERSION = '0.4.0'
MMIF_PYTHON_VERSION = '0.4.5'
CLAMS_PYTHON_VERSION = '0.5.0'
TOKENIZER_VERSION = '3.0.3'
TOKENIZER_LICENSE = 'Apache 2.0'


class TokenizerApp(ClamsApp):

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

    def _annotate(self, mmif, **kwargs):
        # some example code to show how to use arguments, here to willy-nilly
        # throw an error if the caller wants that
        if 'error' in kwargs:
            raise Exception("Exception - %s" % kwargs['error'])
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

    def _new_view(self, docid=None):
        view = self.mmif.new_view()
        view.metadata.app = self.metadata.identifier
        self.sign_view(view)
        view.new_contain(Uri.TOKEN, document=docid)
        return view

    def _read_text(self, textdoc):
        """Read the text content from the document or the text value."""
        if textdoc.location:
            fh = urllib.request.urlopen(textdoc.location)
            text = fh.read().decode('utf8')
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
            a = new_view.new_annotation(Uri.TOKEN, Identifiers.new("t"))
            # no need to do this for documents in the documents list
            if ':' in full_doc_id:
                a.add_property('document', full_doc_id)
            a.add_property('start', p1)
            a.add_property('end', p2)
            a.add_property('text', text[p1:p2])


def text_documents(documents):
    """Utility method to get all text documents from a list of documents."""
    return [doc for doc in documents if str(doc.at_type).endswith(TEXT_DOCUMENT)]


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

    tokenizer_app = TokenizerApp()
    tokenizer_service = Restifier(tokenizer_app)

    parser = argparse.ArgumentParser()
    parser.add_argument('--develop',  action='store_true')
    args = parser.parse_args()

    if args.develop:
        tokenizer_service.run()
    else:
        tokenizer_service.serve_production()
