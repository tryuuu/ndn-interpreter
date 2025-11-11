from __future__ import annotations
import argparse
from pathlib import Path
from .parser.parser import parse
from .interp.evaluator import Interpreter

def main():
    ap = argparse.ArgumentParser(prog="ndnc", description="NDN-less minimal DSL interpreter (print only)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    ap_run = sub.add_parser("run", help="Interpret and run a .ndn file")
    ap_run.add_argument("source", type=Path)

    args = ap.parse_args()

    if args.cmd == "run":
        code = args.source.read_text(encoding="utf-8")
        prog = parse(code)
        Interpreter().run(prog)


if __name__ == "__main__":
    main()