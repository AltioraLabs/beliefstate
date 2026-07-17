"""Enable ``python -m beliefstate`` to invoke the CLI."""

import sys

from beliefstate.cli import main

if __name__ == "__main__":
    sys.exit(main())
