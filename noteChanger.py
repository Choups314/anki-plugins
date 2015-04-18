import anki
from aqt import mw
from anki.sound import clearAudioQueue
from anki.hooks import addHook, wrap
from aqt.reviewer import Reviewer
from aqt.utils import showInfo

# Pendant une session d'apprentissage, il peut arriver de vouloir changer de
# note, sans pour autant quitter la session. Ce plugin permet donc d'effectuer
# ce changement, sans faire crasher la session.

###########################################################################
# La fonction a appeller depuis les autres plugins.
###########################################################################

# L'ID de la derniere "vraie" carte de la session d'apprentissage
lastLearningCard = -1

def onShowQuestion():
    global lastLearningCard
    if mw.reviewer.card.id == lastLearningCard:
        # On est revenu a la session d'apprentissage
        lastLearningCard = -1
        # On n'oublie pas de remettre l'ancien bottomHTML !
        mw.reviewer.bottom.web.stdHtml(
            mw.reviewer._bottomHTML(),
            mw.reviewer.bottom._css + mw.reviewer._bottomCSS)
        mw.reviewer._showAnswerButton()

addHook("showQuestion", onShowQuestion)

def myLinkHandler(self, link, _old):
    if link == "ok":
        mw.reviewer.nextCard()
    else:
       _old(self, link)

Reviewer._linkHandler = wrap(Reviewer._linkHandler, myLinkHandler, "linkHandler")

def changeCard(nid, showAnswer = False):
    """ @nid : noteId of the new card to show. """
    global lastLearningCard
    # Si on n'est pas dans une session d'apprentessage, on ne fait rien.
    if mw.state != "review":
        return
    # On remet la carte dans la file d'attente, si c'est une carte "naturelle"
    # (qui n'a pas ete affichee avec cette fonction)
    currentCard = mw.reviewer.card
    if lastLearningCard == -1:
        lastLearningCard = currentCard.id
        if mw.reviewer.cardQueue:
            mw.reviewer.cardQueue.append(currentCard)
        else:
            mw.reviewer.cardQueue = [currentCard]
    # On refait le boulot de la fonction nextCard()
    note = mw.col.getNote(nid)
    card = note.cards()[0]
    card.startTimer()
    mw.reviewer.card = card
    clearAudioQueue()
    mw.reviewer._showQuestion()
    if showAnswer:
        mw.reviewer._showAnswer()
        # On ne veut pas noter cette carte
        mw.reviewer.bottom.web.stdHtml(
            """<table width=100%% cellspacing=0 cellpadding=0>
            <tr>

                <td align=left width=50 valign=top class=stat>
                    <br><button title="%s" onclick="py.link('edit');">%s</button>
                </td>
                <td align=center width=50> <button onclick="py.link('ok');">OK</button> </td>

                <td width=50 align=right valign=top class=stat>
                    <span id=time class=stattxt></span><br>
                    <button onclick="py.link('more');">%s &#9662;</button>
                </td>
            </tr></table>""" % (_("Shortcut key : E"), _("Edit"), _("More")),
            mw.reviewer.bottom._css + mw.reviewer._bottomCSS)


###########################################################################
# Quand on ferme le reviewer, on nettoite tout nos deplacements ..
###########################################################################

def cleanup():
    global lastLearningCard
    lastLearningCard = -1
    del mw.reviewer.cardQueue[:]
    mw.reviewer.card = None

addHook("deckCloosing", cleanup)
addHook("reviewCleanup", cleanup)
