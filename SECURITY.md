# Security policy

## Supported versions

AntTrail is pre-alpha. Only the latest release on PyPI receives security fixes. If you are on an older version, upgrade
before reporting, in case the problem is already fixed.

| Version        | Supported |
|----------------|-----------|
| Latest release | Yes       |
| Anything older | No        |

## Report a vulnerability

Do not open a public issue for a security problem.

Use GitHub's private vulnerability reporting instead: go to the
[Security tab](https://github.com/ByteMeDirk/anttrail/security) of the repository and choose **Report a vulnerability**.

Include as much of the following as you can:

- The AntTrail version (`anttrail --version`) and Python version.
- Your operating system.
- The command or code that triggers the problem.
- A minimal directory tree or source file that reproduces it, if the input matters.
- What you expected to happen and what happened instead.

## What to expect

This project has one maintainer, so these are targets and not guarantees:

- An acknowledgement within 7 days.
- An assessment of the report within 14 days, including whether it is accepted as a vulnerability.
- A fix released as a patch version, with credit in the changelog if you want it.

Please give the maintainer reasonable time to ship a fix before you disclose the details publicly.

## Scope

AntTrail crawls directories and parses Python source that it does not control, so the following are in scope:

- Reading files outside the directory you asked it to crawl, for example by following a symlink.
- Excessive memory or CPU use caused by a crafted file or directory tree.
- Code execution while parsing a file. AntTrail reads source with `ast.parse` and must never import or run it.
- Writing to a path other than the one given with `--output`.
- Problems in the release process that would let someone publish a package that did not come from this repository.

The following are out of scope:

- Findings in the code that AntTrail crawls. It reports what it finds and does not judge it.
- Vulnerabilities in dependencies that do not affect AntTrail. Report those to the dependency's maintainers.
- Running AntTrail as a privileged user on a directory you do not trust. Run it with the access you would give any other
  tool that reads that directory.
