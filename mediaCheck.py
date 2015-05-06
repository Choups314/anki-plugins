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
import proofs

#######################################################################
# On definit quelques exceptions ..
#######################################################################

exceptions = [
    "graph.png",
    "graphMap.png"
]

#######################################################################
# Le probleme est que la fonction filesInStr originale ne prend pas en
# compte le html des cartes (qui peut contenir des balises [latex] ..).
# Elle ne prend pas non plus en compte les images des preuves
# Ces images latex ne sont donc pas prises en compte correctement dans
# la fonction "Verification des medias".
#######################################################################


def getMedias(model, fields, col):
    l = []
    # Expand the "outer-latex" if needed
    i = 0 # Field counter
    def findFiles(tmp, l):
        for reg in MediaManager.regexps:
            for match in re.finditer(reg, tmp):
                fname = match.group("fname")
                l.append(fname)
    def findFilesInTemplate(reg, tmpl):
        try:
            tmplEnd = re.finditer(reg, tmpl).next().group("end")
            if tmplEnd:
                # On "simule" un champ latex
                tmp = proofs.mungeQA("[latex]" + fields[i] + tmplEnd + "[/latex]",
                                        None, None, model, None, col)
                # On a necessairement une occurrence "standard"
                findFiles(tmp, l)
        except StopIteration: pass
    for f in model['flds']:
        fieldLatexRegexp = re.compile(r"\[latex\]\{\{%s\}\}(?P<end>.+?)\[/latex\]" % (f['name'])
                    , re.DOTALL | re.IGNORECASE)
        for tmpl in model['tmpls']:
            findFilesInTemplate(fieldLatexRegexp, tmpl["qfmt"])
            findFilesInTemplate(fieldLatexRegexp, tmpl["afmt"])
        i += 1
    for string in fields:
        # handle latex
        o = string
        string = proofs.mungeQA(string, None, None, model, None, col)
        # extract filenames
        for reg in MediaManager.regexps:
            for match in re.finditer(reg, string):
                fname = match.group("fname")
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

