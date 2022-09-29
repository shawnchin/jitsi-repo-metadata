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
            'stable': {
                'repo': self.repo,
                'versions': sorted_stable_versions,
                'tags': stable_data,
            },
            'unstable': {
                'repo': self.repo,
                'versions': sorted_unstable_versions,
                'tags': unstable_data,
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
    "jitsi-meet": JitsiTagQuery(repo="jitsi/jitsi-meet"),
    "jitsi-videobridge": JitsiTagQuery(repo="jitsi/jitsi-videobridge"),
    "jicofo": JitsiTagQuery(repo="jitsi/jicofo"),
}


if __name__ == '__main__':
    logging.basicConfig(level=LOGLEVEL, format='%(asctime)s [%(levelname)s] %(message)s')

    for project, query in PROJECTS.items():
        tag_data = query.get_tags()

        stable_output = f'tags_stable_{project}.json'
        unstable_output = f'tags_unstable_{project}.json'

        logger.info(f"Writing {stable_output}")
        with open(stable_output, 'w') as f:
            f.write(json.dumps(tag_data['stable'], indent=2))

        logger.info(f"Writing {unstable_output}")
        with open(unstable_output, 'w') as f:
            f.write(json.dumps(tag_data['unstable'], indent=2))

