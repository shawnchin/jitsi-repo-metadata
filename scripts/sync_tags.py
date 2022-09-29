import datetime
import json
import logging
import re
import subprocess
from typing import (
    NamedTuple,
    Optional,
)

LOGLEVEL = logging.INFO


logger = logging.getLogger('update_tags')


class RefTag(NamedTuple):
    tag: str
    stable: bool
    version: int


class JitsiTagQuery:

    def __init__(self, repo: str):
        self.repo = repo
        self.repo_url = f'https://github.com/{repo}'
        # self.repo_url = f'git@github.com:{project}.git'

    def get_tags(self):
        command = self._get_git_ls_command()
        logger.info(f"Running {' '.join(command)}")
        output = subprocess.check_output(command).decode('utf-8')
        sync_time = datetime.datetime.utcnow().isoformat()

        stable_data = {}
        stable_versions = set()
        unstable_data = {}
        unstable_versions = set()

        logger.info('parsing output')
        for line in output.splitlines():
            try:
                commit_hash, ref = line.split()
            except ValueError:
                continue

            tag_data = self._parse_ref(ref)
            if tag_data:
                data = dict(commit=commit_hash, tag=tag_data.tag)
                if tag_data.stable:
                    stable_versions.add(tag_data.version)
                    stable_data[tag_data.version] = data
                else:
                    unstable_versions.add(tag_data.version)
                    unstable_data[tag_data.version] = data

        sorted_stable_versions = sorted(stable_versions, reverse=True)
        sorted_unstable_versions = sorted(unstable_versions, reverse=True)

        logger.info(f'Found {len(stable_versions)} stable versions and {len(unstable_versions)} unstable versions')
        logger.info(f'Latest stable: {stable_data[sorted_stable_versions[0]]["tag"]}')
        logger.info(f'Latest unstable: {unstable_data[sorted_unstable_versions[0]]["tag"]}')

        return {
            'repo': self.repo,
            'syncAt': sync_time,
            'versions': {
                'stable': sorted_stable_versions,
                'unstable': sorted_unstable_versions,
            },
            'tags': {
                'stable': stable_data,
                'unstable': unstable_data,
            },
        }

    def _get_git_ls_command(self):
        return [
            'git',
            'ls-remote',
            '--tags',
            '--sort=v:refname',
            self.repo_url,
            'refs/tags*/jitsi-meet_*',
        ]

    @staticmethod
    def _parse_ref(ref: str) -> Optional[RefTag]:
        """ Returns None if we don't care about this tag, else return parsed value as RefTag. """
        match = re.match(r'refs/tags/((stable/)?jitsi-meet_(\d+))$', ref)
        if not match:
            return None

        tag, stable, version = match.groups()
        return RefTag(tag=tag, stable=bool(stable), version=int(version))


PROJECTS = {
    "jitsi-meet": {
        "query": JitsiTagQuery(repo="jitsi/jitsi-meet"),
        "output": "tags_jitsi-meet.json",
    },
    "jitsi-videobridge": {
        "query": JitsiTagQuery(repo="jitsi/jitsi-videobridge"),
        "output": "tags_jitsi-videobridge.json",
    },

    "jicofo": {
        "query": JitsiTagQuery(repo="jitsi/jicofo"),
        "output": "tags_jicofo.json",
    },
}


if __name__ == '__main__':
    logging.basicConfig(level=LOGLEVEL, format='%(asctime)s [%(levelname)s] %(message)s')

    for project, params in PROJECTS.items():
        tag_data = params['query'].get_tags()
        output = params['output']
        logger.info(f"Writing output as JSON to {output}")
        with open(output, 'w') as f:
            f.write(json.dumps(tag_data, indent=2))

