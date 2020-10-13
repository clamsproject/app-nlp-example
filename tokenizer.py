"""tokenizer.py

Return a list of offset pairs of all tokens in the input string, using a
simplistic regular expression.

"""

__VERSION__ = "0.1.0"

import re

def tokenize(text):
    return [tok.span() for tok in re.finditer("\w+", text)]


if __name__ == '__main__':
    
    result = tokenize("The door is open.")
    print(result)
