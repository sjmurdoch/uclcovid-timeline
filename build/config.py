#!/usr/bin/env python3
"""Settings for the timeline build, from TOML with environment and CLI overrides.

Precedence, per the project convention: command line beats environment beats
the TOML file beats the built-in default. Environment variables take the
prefix UCLTL_ with the dotted path upper-cased and dots as underscores, so
`paths.archive` is `UCLTL_PATHS_ARCHIVE`.

Standard library only. Python 3.11+ for tomllib.
"""
import argparse
import os
import tomllib
from pathlib import Path

PREFIX = 'UCLTL_'
ROOT = Path(__file__).resolve().parent.parent          # timeline/
DEFAULT_TOML = ROOT / 'timeline.toml'

# Built-in defaults, used when the TOML file is absent or a key is missing.
DEFAULTS = {
    'paths.archive': '../home/uclcovid',
    'paths.updates': '../home/uclcovid/data/updates',
    'paths.cases': '../home/uclcovid/data/covid_raw.csv',
    'paths.resources': '../UK COVID-19 Timeline Resources.md',
    'paths.text': 'text',
    'paths.data': 'data',
    'paths.ledger': 'timeline.csv',
    'paths.progress': 'PROGRESS.md',
    'paths.markdown_out': 'TIMELINE.md',
    'paths.html_out': 'timeline.html',
    'markdown.source_prefix':
        'https://github.com/sjmurdoch/uclcovid/blob/main/data/updates/',
    'range.start': '2020-01-01',
    'range.end': '2022-12-31',
    'extract.date_window': 1200,
}


def _flatten(d, prefix=''):
    """Dotted-path view of the parsed TOML, leaving lists of tables intact."""
    out = {}
    for k, v in d.items():
        key = f'{prefix}{k}'
        if isinstance(v, dict):
            out.update(_flatten(v, key + '.'))
        else:
            out[key] = v
    return out


class Config:
    def __init__(self, values, source):
        self._v = values
        self.source = source

    def get(self, key, default=None):
        return self._v.get(key, default)

    def __getitem__(self, key):
        if key not in self._v:
            raise KeyError(f'no setting {key!r} (checked CLI, {PREFIX}*, '
                           f'{self.source}, and built-in defaults)')
        return self._v[key]

    def path(self, key):
        """A path setting resolved against timeline/, so relative settings in
        the TOML mean what they look like regardless of the caller's cwd."""
        return (ROOT / str(self[key])).resolve()

    def phases(self):
        return self._v.get('phases', [])

    def restrictions(self):
        """Restriction regimes in date order, for the chart's background
        shading. Sorted here rather than trusted from the file, because a span
        out of order would silently draw a band backwards."""
        return sorted(self._v.get('restrictions', []),
                      key=lambda r: str(r['start']))

    def restriction_levels(self):
        """Level number -> name, for the shading legend."""
        return {int(r['level']): r['name']
                for r in self._v.get('restriction_levels', [])}


def load(argv=None, extra_args=None):
    """Read settings. `extra_args` is a callable taking the ArgumentParser, for
    scripts with options of their own; returns (Config, parsed_args)."""
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument('--config', default=str(DEFAULT_TOML),
                    help='path to timeline.toml')
    ap.add_argument('--set', action='append', default=[], metavar='KEY=VALUE',
                    help='override any dotted setting, repeatable')
    if extra_args:
        extra_args(ap)
    args = ap.parse_args(argv)

    values = dict(DEFAULTS)

    toml_path = Path(args.config)
    if toml_path.exists():
        with open(toml_path, 'rb') as fh:
            parsed = tomllib.load(fh)
        phases = parsed.pop('phases', None)
        values.update(_flatten(parsed))
        if phases is not None:
            values['phases'] = phases

    for key in list(values):
        env = PREFIX + key.upper().replace('.', '_')
        if env in os.environ:
            values[key] = _coerce(os.environ[env], values.get(key))

    for item in args.set:
        if '=' not in item:
            ap.error(f'--set expects KEY=VALUE, got {item!r}')
        key, _, val = item.partition('=')
        values[key] = _coerce(val, values.get(key))

    return Config(values, str(toml_path)), args


def _coerce(text, like):
    """Match the type of the value being overridden, so --set works for
    numbers and flags without callers having to cast."""
    if isinstance(like, bool):
        return text.strip().lower() in ('1', 'true', 'yes', 'on')
    if isinstance(like, int):
        return int(text)
    if isinstance(like, float):
        return float(text)
    return text


if __name__ == '__main__':
    cfg, _ = load()
    for k in sorted(cfg._v):
        if not isinstance(cfg._v[k], list):
            print(f'{k} = {cfg._v[k]!r}')
    for p in cfg.phases():
        print(f'phase {p["start"]} {p["name"]}')
    levels = cfg.restriction_levels()
    for r in cfg.restrictions():
        print(f'restriction {r["start"]} level {r["level"]} '
              f'({levels.get(int(r["level"]), "?")}) {r["name"]}')
