"""test.py

Run a simple tokenizery on an input MMIF file. This bypasses the server and just
pings the annotate() method on the SpacyApp class. Prints a summary of the views
in the end result.

Usage:

$ python test.py example-mmif.json out.json

"""

import sys
import mmif
from app import TokenizerApp

with open(sys.argv[1]) as fh_in, open(sys.argv[2], 'w') as fh_out:
    mmif_out_as_string = TokenizerApp().annotate(fh_in.read())
    mmif_out = mmif.Mmif(mmif_out_as_string)
    fh_out.write(mmif_out_as_string)
    for view in mmif_out.views:
        print("<View id=%s annotations=%s app=%s>"
              % (view.id, len(view.annotations), view.metadata['app']))
