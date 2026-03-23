from .engine import run_tot

if __name__ == "__main__":
    import sys, json
    question = " ".join(sys.argv[1:]) or "Demo question"
    print(json.dumps(run_tot(question), indent=2))
