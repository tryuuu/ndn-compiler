from __future__ import annotations
import argparse
from pathlib import Path
from .parser.parser import parse
from .interp.evaluator import Interpreter
from .server import Server

def main():
    ap = argparse.ArgumentParser(prog="ndnc", description="NDN-less minimal DSL interpreter (print only)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    ap_run = sub.add_parser("run", help="Interpret and run a .ndn file")
    ap_run.add_argument("source", type=Path)
    ap_run.add_argument("ndn_args", nargs="*", metavar="ARG",
                        help="NDN names passed as arg0, arg1, ... to the script")

    ap_serve = sub.add_parser("serve", help="Start NDN server (producer)")

    args = ap.parse_args()

    if args.cmd == "run":
        code = args.source.read_text(encoding="utf-8")
        prog = parse(code)
        # 位置引数を arg0, arg1, ... として Interpreter に渡す
        ndn_args = {f"arg{i}": v for i, v in enumerate(args.ndn_args)}
        Interpreter(args=ndn_args).run(prog)
    elif args.cmd == "serve":
        Server().run()


if __name__ == "__main__":
    main()