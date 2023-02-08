import json
import logging
import re
from operator import itemgetter

import requests as requests

LOGLEVEL = logging.INFO
logger = logging.getLogger('sync_deps')

STABLE_PACKAGES_URL = "https://download.jitsi.org/stable/Packages"
UNSTABLE_PACKAGES_URL = "https://download.jitsi.org/unstable/Packages"
STABLE_OUT_FILE = "deps_stable_jitsi-meet.json"
UNSTABLE_OUT_FILE = "deps_unstable_jitsi-meet.json"
VERSION_CUTOFF = (2, 0, 6030, 1)


def extract_jitsi_meet_deps(line_iter):
    out = []
    for stanza in get_stanzas_for_jitsi_meet(line_iter):
        version = stanza["Version"]
        if not version_in_scope(version):
            continue
        dependencies = {}
        dependencies.update(parse_deps(stanza.get("Pre-Depends")))
        dependencies.update(parse_deps(stanza.get("Depends")))

        recommends = {}
        recommends.update(parse_deps(stanza.get("Recommends")))

        out.append(dict(version=version, deps=dependencies, recommends=recommends))
    return out

def version_in_scope(version):
    version_tuple = parse_version(version)
    return version_tuple >= VERSION_CUTOFF


def parse_version(version):
    major, minor, rem = version.split(".")
    patch, _, subv = rem.partition("-")
    return int(major), int(minor), int(patch), subv


def parse_deps(line: str):
    deps = {}
    if line:
        for entry in (s.strip() for s in re.split(r'[,|]', line)):
            match = re.match(r"([\w-]+) \(= (.+)\)$", entry)
            if match:
                deps[match.group(1)] = match.group(2)
    return deps

def get_stanzas_for_jitsi_meet(iter_lines):
    for stanza in parse_packages_indices(iter_lines):
        if stanza[0] == "Package: jitsi-meet":  # we only care about "jitsi-meet" package
            yield parse_stanza(stanza)


def parse_stanza(stanza):
    out = {}
    for line in stanza:
        key, value = line.split(": ", 1)
        out[key] = value
    return out


def parse_packages_indices(line_iter):
    # Format: https://wiki.debian.org/DebianRepository/Format#A.22Packages.22_Indices
    buffer = []
    for line in line_iter:
        line = line.rstrip('\n')
        if line:
            if line.startswith("#"):  # skip comments
                continue
            elif line.startswith(" ") or line.startswith("\t"):  # folded fields
                assert buffer  # should never happen if no previous lines
                buffer[-1] = f'{buffer[-1]}\n{line}'
            else:
                buffer.append(line)
        else:  # empty line separates stanzas
            if buffer:
                yield buffer
                buffer = []

    if buffer:
        yield buffer


def is_empty_line(line):
    return line == "\n"


if __name__ == '__main__':
    logging.basicConfig(level=LOGLEVEL, format='%(asctime)s [%(levelname)s] %(message)s')

    pairs = [
        (STABLE_PACKAGES_URL, STABLE_OUT_FILE),
        (UNSTABLE_PACKAGES_URL, UNSTABLE_OUT_FILE),
    ]

    for package_url, out_file in pairs:
        logger.info(f'Reading packages index from {package_url}')
        response = requests.get(package_url)
        response.raise_for_status()
        decoded_lines = (line.decode('utf-8') for line in response.iter_lines())

        logger.info(f'Filtering and parsing deps for jitsi-meet')
        jitsi_meet_deps = extract_jitsi_meet_deps(decoded_lines)
        sorted_jitsi_meet_deps = sorted(jitsi_meet_deps, key=itemgetter("version"), reverse=True)

        logger.info(f"Writing {out_file}")
        with open(out_file, 'w') as f:
            f.write(json.dumps(sorted_jitsi_meet_deps, indent=2))
