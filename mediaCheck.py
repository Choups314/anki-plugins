from anki.hooks import wrap
from anki.media import MediaManager
from aqt.utils import showInfo
from anki.consts import *
from anki.latex import mungeQA
import re

### Le probleme est que la fonction filesInStr originale ne prend pas en 
### compte le html des cartes (qui peut contenir des balises [latex] ..).
### Ces images latex ne sont donc pas prises en compte correctement dans
### la fonction "Verification des medias".

def myFilesInStr(self, mid, string, _old, includeRemote=False):
        l = []
        model = self.col.models.get(mid)
        strings = []
        if model['type'] == MODEL_CLOZE and "{{c" in string:
            # if the field has clozes in it, we'll need to expand the
            # possibilities so we can render latex
            strings = self._expandClozes(string)
        else:
            strings = [string]
        for string in strings:
            # handle latex
            string = mungeQA(string, None, None, model, None, self.col)
	    if mid==1419157173874:
	        showInfo(string)
            # extract filenames
            for reg in self.regexps:
                for match in re.finditer(reg, string):
                    fname = match.group("fname")
                    isLocal = not re.match("(https?|ftp)://", fname.lower())
                    if isLocal or includeRemote:
                        l.append(fname)
        return l

MediaManager.filesInStr = wrap(MediaManager.filesInStr, myFilesInStr, "filesInStr")
