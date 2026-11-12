"""Secondary and exploratory analyses of Paper B, written AFTER the freeze (PREREG Revision 2 row 31, D14).
Imports the frozen modules of src/run unchanged; never writes tables/summary.csv or results/run/.
Outputs: results/secondary/<year>/ and tables/summary_secondary.csv (17 ledger columns, status secondary/exploratory,
family_id 'secondary', no p_holm). Specifications: PREREG sections 3, 5, 6 ('Secondary'); every setting that PREREG leaves
open is a choice made after the freeze and is tagged CHOICE_AFTER_FREEZE in the docstring of the function that makes it."""
import os
import site
import sys

_up = site.getusersitepackages()
if os.path.isdir(_up) and _up not in sys.path:
    sys.path.append(_up)
_SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)
