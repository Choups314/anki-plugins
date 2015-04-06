from aqt.reviewer import Reviewer
from anki.hooks import wrap
from aqt.utils import getBase
from aqt.utils import showInfo

header = """
 <link rel="stylesheet" href="jquery-ui.css">
 <script src="jquery.js"></script>
 <script src="jquery-ui.js"></script>
 <script>
 $(function() {
     var icons = {
         header: "ui-icon-circle-arrow-e",
         activeHeader: "ui-icon-circle-arrow-s"
     };
     $( "#accordion" ).accordion({
     icons: icons
     });
     $( "#toggle" ).button().click(function() {
     if ( $( "#accordion" ).accordion( "option", "icons" ) ) {
     $( "#accordion" ).accordion( "option", "icons", null );
     } else {
     $( "#accordion" ).accordion( "option", "icons", icons );
     }
     });
     });
     </script>
"""

addHeader = """
function callback3() {
    $("head").append( $("<link rel='stylesheet' type='text/css' href='jquery/jquery-ui.css'>"));
    $(function() {  $( '#accordion' ).accordion(); });
}

function callback2() {
    script = document.createElement("script");
    script.type = "text/javascript";
    script.src = "jquery/jquery-ui.js";
    script.onload = callback3;
    script.onreadystatechange = callback3;
    document.body.appendChild(script);
}

function callback1() {
    var script = document.createElement("script");
    script.type = "text/javascript";
    script.src = "jquery/jquery.js";
    script.onreadystatechange = callback2;
    script.onload = callback2;
    document.body.appendChild(script);
}

callback1();

""";

def loadHeader(self):
    self.web.eval(addHeader)

Reviewer._initWeb = wrap(Reviewer._initWeb, loadHeader)
