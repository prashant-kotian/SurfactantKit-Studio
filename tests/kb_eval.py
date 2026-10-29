"""Print how the knowledge base answers the evaluation questions. python tests/kb_eval.py [-v]"""
import sys

from kb_questions import IN_SCOPE, OUT_OF_SCOPE

from surfkit_studio.knowledge import kb

verbose = "-v" in sys.argv
K = kb()
ok = 0
for q, must in IN_SCOPE:
    hits = K.search(q)
    a = K.answer(q)
    good = a["found"] and must.lower().replace(" ", "") in a["reply"].lower().replace(" ", "")
    ok += good
    if verbose or not good:
        top = [(round(s, 1), e.title) for s, e in hits]
        print(("OK  " if good else "MISS"), q, "| need:", must, "|", top)
refused = 0
for q in OUT_OF_SCOPE:
    a = K.answer(q)
    refused += not a["found"]
    if verbose or a["found"]:
        print(("REFUSED " if not a["found"] else "ANSWERED"), q, "|", [(round(s, 1), e.title) for s, e in K.search(q)])
print(f"in scope {ok}/{len(IN_SCOPE)}, out of scope refused {refused}/{len(OUT_OF_SCOPE)}")
