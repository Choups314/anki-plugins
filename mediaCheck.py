from anki.hooks import wrap
from anki.media import MediaManager
from aqt.utils import showInfo
from anki.consts import *
from anki.latex import mungeQA
import re
from anki.utils import splitFields, isMac
import unicodedata
import sys

### Le probleme est que la fonction filesInStr originale ne prend pas en
### compte le html des cartes (qui peut contenir des balises [latex] ..).
### Ces images latex ne sont donc pas prises en compte correctement dans
### la fonction "Verification des medias".

def myFilesInStr(self, mid, string, _old, includeRemote=False):
    l = []
    model = self.col.models.get(mid)
    strings = []
    if (model['type'] == MODEL_CLOZE and ("{{c" in string)):
        # if the field has clozes in it, we'll need to expand the
        # possibilities so we can render latex
        strings = self._expandClozes(string)
    else:
        strings = splitFields(string)
    # Expand the "outer-latex" if needed
    i = 0 # Field counter
    for f in model['flds']:
        for tmpl in model['tmpls']:
            if tmpl["qfmt"].find("[latex]{{" + f['name'] + "}}") != -1:
                strings[i] = "[latex]" + strings[i] + "[/latex]"
                break
        i += 1
    for string in strings:
        # handle latex
        string = mungeQA(string, None, None, model, None, self.col)
        # extract filenames
        for reg in self.regexps:
            for match in re.finditer(reg, string):
                fname = match.group("fname")
                isLocal = not re.match("(https?|ftp)://", fname.lower())
                if isLocal or includeRemote:
                    l.append(fname)
    return l

MediaManager.filesInStr = wrap(MediaManager.filesInStr, myFilesInStr, "filesInStr")
