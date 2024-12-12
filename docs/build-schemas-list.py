#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2024 Red Hat, Inc
#
# SPDX-License-Identifier: GPL-2.0-or-later

import importlib
import os
import site
import sys
import tempfile
import venv
from collections import defaultdict
from dataclasses import dataclass
from importlib.metadata import entry_points
from subprocess import run
from textwrap import dedent
from urllib.parse import urljoin

from sphinx.ext.napoleon.docstring import GoogleDocstring


SCHEMAS_FILE = "schema-packages.txt"
DOC_FILE = "user-guide/schemas.rst"
HEADER = """
=================
Available Schemas
=================

.. This file is autogenerated by the build-schemas-list.py script. Do not edit manually.

These are the topics that you can expect to see on Fedora's message bus,
sorted by the python package that contains their schema.
Install the corresponding python package if you want to make use of the schema
and access additional information on the message you're receiving.

In the Fedora Infrastructure, some of those topics will be prefixed by
``org.fedoraproject.stg.`` in staging and ``org.fedoraproject.prod.`` in production.
"""
DATAGREPPER_URL = "https://apps.fedoraproject.org/datagrepper/"
PREFIXES = ("org.fedoraproject.", "org.release-monitoring.")


def read_packages(schemas_filepath):
    packages = []
    with open(schemas_filepath) as schemas_file:
        for line in schemas_file:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            packages.append(line)
    packages.sort()
    return packages


@dataclass
class Schema:
    topic: str
    package: str
    app_name: str
    category: str
    doc: str


def create_venv(dirname):
    print("Creating virtualenv...")
    venv.create(dirname, with_pip=True)
    activate_venv(dirname)


def activate_venv(dirname):
    # Remove system site-packages from the path
    for spdir in site.getsitepackages():
        if spdir in sys.path:
            sys.path.remove(spdir)
    sys.prefix = sys.exec_prefix = dirname
    site.addsitepackages(set(sys.path), [dirname])
    site.PREFIXES = [dirname]
    site.ENABLE_USER_SITE = False
    os.environ["VIRTUAL_ENV"] = dirname
    importlib.invalidate_caches()


def install_packages(dirname, packages):
    # Don't use pip as a library:
    # https://pip.pypa.io/en/stable/user_guide/#using-pip-from-your-program
    pip = os.path.join(dirname, "bin", "pip")
    print("Upgrading pip...")
    run([pip, "-q", "install", "--upgrade", "pip"], check=True)  # noqa: S603
    for package in packages:
        print(f"Installing {package}...")
        run([pip, "-q", "install", package], check=True)  # noqa: S603


def extract_docstring(cls):
    if not cls.__doc__:
        return None
    gds = GoogleDocstring(dedent(cls.__doc__), obj=cls)
    doc = []
    for line in gds.lines():
        if line.startswith(".. "):
            break
        if not line:
            continue
        doc.append(line)
    return " ".join(doc)


def get_schemas():
    schemas = defaultdict(list)
    for entry_point in entry_points(group="fedora.messages"):
        msg_cls = entry_point.load()
        if not msg_cls.topic:
            target = f"{entry_point.module}:{entry_point.attr}"
            if target != "fedora_messaging.message:Message":
                print(f"The {target} schema has no declared topic, skipping.")
            continue
        if msg_cls.deprecated:
            continue
        package_name = entry_point.dist.name
        doc = extract_docstring(msg_cls)
        category = _get_category(msg_cls.topic)
        try:
            app_name = msg_cls().app_name
        except Exception:
            # Sometimes we can't instantiate schema classes without an actual body
            app_name = None
        schemas[package_name].append(
            Schema(
                topic=msg_cls.topic,
                package=package_name,
                doc=doc,
                category=category,
                app_name=app_name,
            )
        )
    return schemas


def _is_prefixed(topic):
    return any(topic.startswith(prefix) for prefix in PREFIXES)


def _get_app_name(schemas):
    for schema in schemas:
        if schema.app_name is not None:
            return schema.app_name
    return None


def _get_category(topic):
    if _is_prefixed(topic):
        index = 3
    else:
        index = 0
    return topic.split(".")[index]


def write_doc(schemas, doc_filepath):
    with open(doc_filepath, "w") as doc_file:
        doc_file.write(HEADER)
        for package_name in sorted(schemas):
            package_schemas = schemas[package_name]
            app_name = _get_app_name(package_schemas)
            category = package_schemas[0].category
            title = app_name or category
            print(f"\n\n{title}", file=doc_file)
            print("=" * len(title), end="\n\n", file=doc_file)
            history_url = urljoin(DATAGREPPER_URL, f"raw?category={category}")
            print(
                f"You can view the history of `all {title} messages <{history_url}>`__ "
                "in datagrepper.\n",
                file=doc_file,
            )
            for schema in package_schemas:
                prod_topic = (
                    schema.topic
                    if _is_prefixed(schema.topic)
                    else f"org.fedoraproject.prod.{schema.topic}"
                )
                history_url = urljoin(DATAGREPPER_URL, f"raw?topic={prod_topic}")
                if schema.doc:
                    print(
                        f"* ``{schema.topic}``: {schema.doc.strip()} (`history <{history_url}>`__)",
                        file=doc_file,
                    )
                else:
                    print(
                        f"* ``{schema.topic}`` (`history <{history_url}>`__)",
                        file=doc_file,
                    )


def main():
    here = os.path.dirname(__file__)
    schemas_file = os.path.normpath(os.path.join(here, SCHEMAS_FILE))
    packages = read_packages(schemas_file)
    with tempfile.TemporaryDirectory() as tmpdirname:
        create_venv(tmpdirname)
        install_packages(tmpdirname, packages)
        schemas = get_schemas()
    doc_file = os.path.normpath(os.path.join(here, DOC_FILE))
    write_doc(schemas, doc_file)
    print(f"Wrote the documentation in {doc_file}")


if __name__ == "__main__":
    main()
