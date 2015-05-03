from aqt.qt import *
from anki.hooks import wrap, addHook
from anki.media import MediaManager
from aqt.utils import showInfo
from anki.consts import *
from anki.latex import mungeQA
import re
from anki.utils import splitFields, isMac
import unicodedata
import sys
import utils
from aqt import mw

### Le probleme est que la fonction filesInStr originale ne prend pas en
### compte le html des cartes (qui peut contenir des balises [latex] ..).
### Ces images latex ne sont donc pas prises en compte correctement dans
### la fonction "Verification des medias".

def getMedias(model, fields, col):
    l = []
    # Expand the "outer-latex" if needed
    i = 0 # Field counter
    for f in model['flds']:
        for tmpl in model['tmpls']:
            if ((tmpl["qfmt"].find("[latex]{{" + f['name'] + "}}") != -1)
                    or (tmpl["afmt"].find("[latex]{{" + f['name'] + "}}") != -1)):
                fields[i] = "[latex]" + fields[i] + "[/latex]"
                break
        i += 1
    for string in fields:
        # handle latex
        string = mungeQA(string, None, None, model, None, col)
        # extract filenames
        for reg in MediaManager.regexps:
            for match in re.finditer(reg, string):
                fname = match.group("fname")
                #isLocal = not re.match("(https?|ftp)://", fname.lower())
                l.append(fname)
    return l


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
    return getMedias(model, strings, self.col)

MediaManager.filesInStr = wrap(MediaManager.filesInStr, myFilesInStr, "filesInStr")


#######################################################################
# On ajoute une action qui affiche la liste des medias de la carte en cours
#######################################################################

# On ajoute notre bouton (lors de l'affichage des cartes dans le reviewer) pour
# definir les match

def showMedias():
    model = mw.col.models.get(utils.currentNote.mid)
    strings = utils.currentNote.fields
    medias = getMedias(model, strings, mw.col)
    for m in medias:
        showInfo(str(m))

def addCreateLinksButton(self, m):
    m.addSeparator()
    a = m.addAction("Medias de la carte")
    a.setShortcut(QKeySequence("Shift+I"))
    a.connect(a, SIGNAL("triggered()"), showMedias)

addHook("Reviewer.contextMenuEvent", addCreateLinksButton)

