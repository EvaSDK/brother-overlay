#!/usr/bin/env python

import configparser
import re
from collections import defaultdict
from pathlib import Path

import jinja2

BROTHER_PKG_BASEURL = "https://download.brother.com/pub/com/linux/linux/packages"


def get_version(filename):
    match = re.search(
        r".*-(?P<version>[\d\.]+)-(?P<build>\d)(\.\w+)?\.[a-z0-9]+\.rpm", filename
    )
    if match:
        return match.group("version"), match.group("build")
    print("Could not match", filename)
    raise Exception


def build_template_vars(model_data):
    model_name = model_data["PRINTERNAME"].lower()
    cupswrapper_pkg = model_data["PRN_CUP_RPM"]

    if cupswrapper_pkg:
        cupswrapper_pkg_version = get_version(cupswrapper_pkg)
        cupswrapper_pkg_url = (
            BROTHER_PKG_BASEURL
            + "/"
            + cupswrapper_pkg.replace(model_name, "${PRINTER_MODEL}").replace(
                "-".join(cupswrapper_pkg_version), "${CUPSWRAPPER_PV}"
            )
        )
    else:
        cupswrapper_pkg_version = None
        cupswrapper_pkg_url = None

    lpd_pkg = model_data["PRN_LPD_RPM"]
    if lpd_pkg == "":
        lpd_pkg = model_data["PRN_DRV_RPM"]
    lpd_pkg_version = get_version(lpd_pkg)
    lpd_pkg_url = (
        BROTHER_PKG_BASEURL
        + "/"
        + lpd_pkg.replace(model_name, "${PRINTER_MODEL}")
        .replace(lpd_pkg_version[0], "${PV}")
        .replace(f"-{lpd_pkg_version[1]}.", "-${RPM_BUILD_NUMBER}.")
    )
    return {
        "name": model_name,
        "commercial_names": {model_data.name},
        "cupswrapper_pkg_url": cupswrapper_pkg_url,
        "cupswrapper_pkg_version": cupswrapper_pkg_version,
        "lpd_pkg_url": lpd_pkg_url,
        "lpd_pkg_version": lpd_pkg_version,
    }


def generate_ebuilds():
    catalog = {}
    config = configparser.ConfigParser()

    for description in Path("workdir").glob("*"):
        config.read(description)

        for prn_section in config.sections():
            prn_clean = prn_section.replace("-", "")
            if "LNK" in config[prn_section]:
                catalog[prn_clean] = config[prn_section]["LNK"]
            else:
                catalog[prn_clean] = config[prn_section]

    j2env = jinja2.Environment(loader=jinja2.FileSystemLoader("generator"))
    template = j2env.get_template("brother-printer.ebuild.j2")

    # Reduce
    commercial_names = defaultdict(set)
    for model_name, model_data in list(catalog.items()):
        if not hasattr(model_data, "items"):
            print(model_name, "points to", model_data)
            commercial_names[model_data].add(model_name)
            del catalog[model_name]
        else:
            commercial_names[model_name].add(model_name)

    for model_name, model_data in catalog.items():
        try:
            tvars = build_template_vars(model_data)
            tvars.update({"commercial_names": list(sorted(commercial_names[model_name]))})
        except ValueError:
            print("Skipping", model_name, "due to missing data.")
            continue
        ebuild = template.render(tvars)
        (Path("net-print") / f"brother-{tvars["name"]}-bin").mkdir(exist_ok=True)
        (
            Path("net-print")
            / f"brother-{tvars["name"]}-bin"
            / f"brother-{tvars["name"]}-bin-{tvars['lpd_pkg_version'][0]}.ebuild"
        ).write_text(ebuild + "\n")


if __name__ == "__main__":
    generate_ebuilds()
