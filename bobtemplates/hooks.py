#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Render bobtemplates.plone hooks.
"""
from datetime import date
from mrbob.bobexceptions import SkipQuestion
from mrbob.bobexceptions import ValidationError
from mrbob.hooks import validate_choices
import keyword
import os
import re
import shutil
import string
import subprocess
import sys


def to_boolean(configurator, question, answer):
    """
    If you want to convert an answer to Python boolean, you can
    use this function as :ref:`post-question-hook`:

    .. code-block:: ini

        [questions]
        idiot.question = Are you young?
        idiot.post_ask_question = mrbob.hooks:to_boolean

    Following variables can be converted to a boolean:
    **y, n, yes, no, true, false, 1, 0**
    """
    if isinstance(answer, bool):
        return answer
    value = answer.lower()
    if value in ['y', 'yes', 'true', '1']:
        return True
    elif value in ['n', 'no', 'false', '0']:
        return False
    else:
        raise ValidationError('Value must be a boolean (y/n)')


def get_git_info(value):
    """Try to get information from the git-config.
    """
    gitargs = ['git', 'config', '--get']
    try:
        result = subprocess.check_output(gitargs + [value]).strip()
        return result
    except (OSError, subprocess.CalledProcessError):
        pass


def validate_packagename(configurator):
    """Find out if the name target-dir entered when invoking the command
    can be a valid python-package.
    """
    package_dir = os.path.basename(configurator.target_directory)
    fail = False

    allowed = set(string.ascii_letters + string.digits + '.-_')
    if not set(package_dir).issubset(allowed):
        fail = True

    if package_dir.startswith('.') or package_dir.endswith('.'):
        fail = True

    parts = len(package_dir.split('.'))
    if parts < 2 or parts > 3:
        fail = True

    if fail:
        msg = "Error: '{0}' is not a valid packagename.\n".format(package_dir)
        msg += "Please use a valid name (like collective.myaddon or "
        msg += "plone.app.myaddon)"
        sys.exit(msg)


def pre_username(configurator, question):
    """Get email from git and validate package name.
    """
    # validate_packagename should be run before asking the first question.
    validate_packagename(configurator)

    default = get_git_info('user.name')
    if default:
        question.default = default


def pre_email(configurator, question):
    """Get email from git.
    """
    default = get_git_info('user.email')
    if default:
        question.default = default


def post_plone_version(configurator, question, answer):
    """Find out if it is supposed to be Plone 5.
    """
    _set_plone_version_variables(configurator, answer)
    return answer


def _set_plone_version_variables(configurator, version):
    if 'plone.is_plone5' not in configurator.variables:
        # Find out if it is supposed to be Plone 5.
        if version.startswith('5'):
            configurator.variables['plone.is_plone5'] = True
        else:
            configurator.variables['plone.is_plone5'] = False
    if 'plone.minor_version' not in configurator.variables:
        # extract minor version (4.3)
        # (according to https://plone.org/support/version-support-policy)
        # this is used for the trove classifier in setup.py of the product
        configurator.variables['plone.minor_version'] = '.'.join(
            version.split('.')[:2])


def post_ask(configurator):
    """Make sure some variables are set, also in non-interactive mode.

    This is called after all questions have been asked.
    """
    configurator.variables['year'] = date.today().year
    version = configurator.variables.get('plone.version')
    if not version:
        return
    _set_plone_version_variables(configurator, version)


def post_type(configurator, question, answer):
    """Skip questions depending on the type answer.
    """
    value = validate_choices(configurator, question, answer)
    if value != u'Dexterity':
        configurator.variables['package.dexterity_type_name'] = ''
        configurator.variables['package.dexterity_type_name_lower'] = ''
    return value


def pre_dexterity_type_name(configurator, question):
    if configurator.variables.get('package.type') != 'Dexterity':
        raise SkipQuestion


def post_dexterity_type_name(configurator, question, answer):
    if keyword.iskeyword(answer):
        raise ValidationError('%s is a reserved keyword' % answer)
    if not re.match('[_A-Za-z][_a-zA-Z0-9_]*$', answer):
        raise ValidationError('%s is not a valid identifier' % answer)
    return answer


def pre_theme_name(configurator, question):
    validate_packagename(configurator)

    default = os.path.basename(
        configurator.target_directory).split('.')[-1].capitalize()
    if default:
        question.default = default


def post_theme_name(configurator, question, answer):
    regex = r'^\w+[a-zA-Z0-9 \.\-_]*\w$'
    if not re.match(regex, answer):
        msg = u"Error: '{0}' is not a valid themename.\n".format(answer)
        msg += u"Please use a valid name (like 'Tango' or 'my-tango.com')!\n"
        msg += u"At beginning or end only letters|diggits are allowed.\n"
        msg += u"Inside the name also '.-_' are allowed.\n"
        msg += u"No umlauts!"
        raise ValidationError(msg)
    return answer


def prepare_render(configurator):
    """Some variables to make templating easier.

    This is especially important for allowing nested and normal packages.
    """
    # get package-name and package-type from user-input

    package_dir = os.path.basename(configurator.target_directory)
    nested = bool(len(package_dir.split('.')) == 3)
    configurator.variables['package.nested'] = nested
    configurator.variables['package.namespace'] = package_dir.split('.')[0]
    if nested:
        namespace2 = package_dir.split('.')[1]
    else:
        namespace2 = None
    configurator.variables['package.namespace2'] = namespace2
    configurator.variables['package.name'] = package_dir.split('.')[-1]

    if nested:
        dottedname = "{0}.{1}.{2}".format(
            configurator.variables['package.namespace'],
            configurator.variables['package.namespace2'],
            configurator.variables['package.name'])
    else:
        dottedname = "{0}.{1}".format(
            configurator.variables['package.namespace'],
            configurator.variables['package.name'])

    # package.dottedname = 'collective.foo.something'
    configurator.variables['package.dottedname'] = dottedname

    # package.uppercasename = 'COLLECTIVE_FOO_SOMETHING'
    configurator.variables['package.uppercasename'] = configurator.variables[
        'package.dottedname'
    ].replace('.', '_').upper()

    camelcasename = dottedname.replace('.', ' ').title()\
        .replace(' ', '')\
        .replace('_', '')
    browserlayer = "{0}Layer".format(camelcasename)

    # package.browserlayer = 'CollectiveFooSomethingLayer'
    configurator.variables['package.browserlayer'] = browserlayer

    # package.longname = 'collectivefoosomething'
    configurator.variables['package.longname'] = camelcasename.lower()

    # jenkins.directories = 'collective/foo/something'
    configurator.variables[
        'jenkins.directories'
    ] = dottedname.replace('.', '/')

    # namespace_packages = "['collective', 'collective.foo']"
    if nested:
        namespace_packages = "'{0}', '{0}.{1}'".format(
            configurator.variables['package.namespace'],
            configurator.variables['package.namespace2'])
    else:
        namespace_packages = "'{0}'".format(
            configurator.variables['package.namespace'])
    configurator.variables['package.namespace_packages'] = namespace_packages

    if configurator.variables.get('package.dexterity_type_name'):
        configurator.variables[
            'package.dexterity_type_name_lower'
        ] = configurator.variables['package.dexterity_type_name'].lower()
    else:
        # We have to make sure those variables are always set because we are
        # going to create files that contain those variables. Even if we
        # remove those files afterwards. This is just how mr.bob rolls.
        configurator.variables['package.dexterity_type_name'] = ''
        configurator.variables['package.dexterity_type_name_lower'] = ''

    if configurator.variables.get('theme.name'):
        def normalize_string(value):
            value = "-".join(value.split('_'))
            value = "-".join(value.split())
            return value
        configurator.variables[
            "theme.normalized_name"] = normalize_string(
                configurator.variables.get('theme.name')).lower()
    else:
        configurator.variables["theme.normalized_name"] = ""


def cleanup_package(configurator):
    """Cleanup and make nested if needed.

    Transform into a nested package if that was the selected option.
    Remove parts that are not needed depending on the chosen configuration.
    """

    nested = configurator.variables['package.nested']

    # construct full path '.../src/collective'
    start_path = make_path(
        configurator.target_directory,
        'src',
        configurator.variables['package.namespace'])

    # path for normal packages: '.../src/collective/myaddon'
    base_path = make_path(
        start_path,
        configurator.variables['package.name'])

    if nested:
        # Event though the target-dir was 'collective.behavior.myaddon' mrbob
        # created a package collective.behavior.myaddon/src/collective/myaddon
        # since the template does not hava a folder for namespace2.
        # Here this package is turned into a nested package
        # collective.behavior.myaddon/src/collective/behavior/myaddon by
        # inserting a folder with the namepsace2 ('behavior') and oopying
        # a __init__.py into it.

        # full path for nested packages: '.../src/collective/behavior/myaddon'
        base_path_nested = make_path(
            start_path,
            configurator.variables['package.namespace2'],
            configurator.variables['package.name'])

        # directory to be created: .../src/collective/behavior
        newpath = make_path(
            start_path,
            configurator.variables['package.namespace2'])
        if not os.path.exists(newpath):
            # create new directory .../src/collective/behavior
            os.makedirs(newpath)

        # copy .../src/collective/__init__.py to
        # .../src/collective/myaddon/__init__.py
        init = make_path(start_path, '__init__.py')
        shutil.copy2(init, newpath)

        # move .../src/collective/myaddon to .../src/collective/behavior
        shutil.move(base_path, base_path_nested)

        # use the new path for deleting
        base_path = base_path_nested

    # find out what to delete
    to_delete = []

    if configurator.variables.get('package.type') != u'Dexterity':
        to_delete.extend([
            make_path(base_path, "profiles", "default", "types.xml"),
            make_path(base_path, "profiles", "default", "types"),
            make_path(base_path, "tests", "test_.py"),
            make_path(base_path, "tests", "robot", "test_.robot"),
        ])

    # remove parts
    for path in to_delete:
        if os.path.exists(path):
            if os.path.isdir(path):
                shutil.rmtree(path)
            else:
                os.remove(path)

    if configurator.template_dir.split('/')[-1] == 'plone_theme_package':
        # make a copy of the HOWTO_DEVELOP.rst also in the package root
        shutil.copy2(
            make_path(base_path, "theme", "HOWTO_DEVELOP.rst",),
            make_path(configurator.target_directory, "HOWTO_DEVELOP.rst"),
        )


def make_path(*args):
    """ generate path string  """
    return os.sep.join(args)
