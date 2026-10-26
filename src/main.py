"""The one command. From the date/ folder:   python ../src/main.py

Reads the client's files from the current folder (date/) and the config from config/, and writes
everything to output/, next to date/. Exit code 0: the draft is written; 1: nothing could be drafted
(a config error, or output/ cannot be emptied). verificari.md always says why."""

import hashlib
import shutil
import sys
from pathlib import Path

from checks import apply_decisions, as_prior, check_prior_column, check_same_as_prior, run_relations
from config import load_config
from read import check_fact, fact_figure, read_workbook
from render import approval, render_section, write_checks, write_trace

ROOT = Path(__file__).resolve().parent.parent  # src/ is next to date/, config/ and output/


def main(root=ROOT, folder=None):
    folder = folder or Path.cwd()
    output = root / "output"
    try:
        if output.exists():
            shutil.rmtree(output)  # every file in output/ comes from this run
        output.mkdir()
    except OSError as error:
        print(f"output/ nu poate fi golit; închideți fișierele deschise din el și rulați din nou ({error})")
        return 1
    cfg, errors = load_config(root / "config")
    checks_file = output / cfg.get("settings", {}).get("output", {}).get("checks", "verificari.md")
    if errors:
        write_checks(checks_file, {"errors": errors}, cfg)
        print(f"Configurația are erori; vezi {checks_file}")
        return 1
    try:
        draft(cfg, folder, output, checks_file)
    except Exception as error:  # a bug, not a data problem: data problems are gaps
        write_checks(checks_file, {"errors": [f"eroare neprevăzută: {error!r}"]}, cfg)
        print(f"Eroare neprevăzută; vezi {checks_file}")
        return 1
    print(f"Gata: {output}")
    return 0


def draft(cfg, folder, output, checks_file):
    """Read, check, decide, write: the whole run on valid config."""
    settings = cfg["settings"]
    current_book, prior_book = folder / settings["workbooks"]["current"], folder / settings["workbooks"]["prior"]
    current, hidden = read_workbook(current_book, cfg["figures"], settings)
    prior_column = read_workbook(current_book, cfg["figures"], settings, "prior")[0]
    last_year = as_prior(read_workbook(prior_book, cfg["figures"], settings)[0])
    problems = {fact["id"]: check_fact(fact, folder) for fact in cfg["facts"]}
    from_facts = {fact["figure"]: fact_figure(fact, problems[fact["id"]], settings) for fact in cfg["facts"] if "figure" in fact}
    figures = {**current, **from_facts, **last_year}

    checks = check_prior_column(figures, prior_column) + check_same_as_prior(figures, settings["prior_year"])
    checks += run_relations(figures, cfg["relations"])
    decisions = apply_decisions(figures, cfg["decisions"])

    gaps = []
    for section in settings["sections"]:
        text, calculated, section_gaps = render_section(cfg["templates"][section], cfg["sentences"], figures, cfg["facts"], problems, cfg)
        if not approval(cfg, section)[0]:
            text = settings["words"]["not_approved"] + "\n\n" + text
        name = settings["output"]["draft"].format(section=section, year=settings["reporting_year"])
        (output / name).write_text(text, encoding="utf-8")
        figures.update(calculated)
        gaps += [(section, sentence, reason) for sentence, reason in section_gaps]

    inputs = [settings["workbooks"]["current"], settings["workbooks"]["prior"], *settings["documents"]]
    checksums = [(name, hashlib.sha256((folder / name).read_bytes()).hexdigest() if (folder / name).exists() else "lipsește")
                 for name in inputs]
    write_trace(output / settings["output"]["trace"], figures, cfg)
    write_checks(checks_file, {"checksums": checksums, "hidden": hidden, "checks": checks, "figures": figures,
                               "decisions": decisions, "problems": problems, "gaps": gaps}, cfg)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # the Windows console cannot show ș otherwise
    sys.exit(main())
