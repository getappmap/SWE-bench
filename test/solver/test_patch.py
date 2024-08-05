from pathlib import Path
import sys
import os

# Add the parent directory to the Python path
thisdir = Path(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(thisdir.parent.parent.as_posix())

from appmap.solve.patch import clean_patch

SETUP_PATCH = """diff --git a/setup.py b/setup.py
index c0a9c2b0d..579fdee60 100644
--- a/setup.py
+++ b/setup.py
@@ -15,21 +15,21 @@ if sys.version_info < (3, 6):
     sys.exit(1)
 
 install_requires = [
-    'sphinxcontrib-applehelp',
-    'sphinxcontrib-devhelp',
+    'sphinxcontrib-applehelp<=1.0.7',
+    'sphinxcontrib-devhelp<=1.0.5',
     'sphinxcontrib-jsmath',
-    'sphinxcontrib-htmlhelp>=2.0.0',
-    'sphinxcontrib-serializinghtml>=1.1.5',
-    'sphinxcontrib-qthelp',
-    'Jinja2>=2.3',
+    'sphinxcontrib-htmlhelp>=2.0.0,<=2.0.4',
+    'sphinxcontrib-serializinghtml>=1.1.5,<=1.1.9',
+    'sphinxcontrib-qthelp<=1.0.6',
+    'Jinja2<3.0',
     'Pygments>=2.0',
     'docutils>=0.14,<0.18',
     'snowballstemmer>=1.1',
     'babel>=1.3',
-    'alabaster>=0.7,<0.8',
+    'alabaster>=0.7,<0.7.12',
     'imagesize',
     'requests>=2.5.0',
-    'packaging',
+    'packaging', 'markupsafe<=2.0.1',
     "importlib-metadata>=4.4; python_version < '3.10'",
 ]
 
"""

TYPEHINTS_PATCH = """diff --git a/sphinx/ext/autodoc/typehints.py b/sphinx/ext/autodoc/typehints.py
index f4b4dd35e..4a9f6af74 100644
--- a/sphinx/ext/autodoc/typehints.py
+++ b/sphinx/ext/autodoc/typehints.py
@@ -17,7 +17,9 @@ from docutils.nodes import Element
 
 from sphinx import addnodes
 from sphinx.application import Sphinx
-from sphinx.util import inspect, typing
+from sphinx.util import inspect, typing, logging
+
+logger = logging.getLogger(__name__)
 
 
 def record_typehints(app: Sphinx, objtype: str, name: str, obj: Any,
@@ -30,9 +32,9 @@ def record_typehints(app: Sphinx, objtype: str, name: str, obj: Any,
             sig = inspect.signature(obj, type_aliases=app.config.autodoc_type_aliases)
             for param in sig.parameters.values():
                 if param.annotation is not param.empty:
-                    annotation[param.name] = typing.stringify(param.annotation)
+                    annotation[param.name] = typing.stringify(param.annotation, short=app.config.autodoc_unqualified_typehints)
             if sig.return_annotation is not sig.empty:
-                annotation['return'] = typing.stringify(sig.return_annotation)
+                annotation['return'] = typing.stringify(sig.return_annotation, short=app.config.autodoc_unqualified_typehints)
     except (TypeError, ValueError):
         pass
 
@@ -155,10 +157,13 @@ def augment_descriptions_with_types(
             has_type.add('return')
 
     # Add 'type' for parameters with a description but no declared type.
-    for name in annotations:
+    for name, annotation in annotations.items():
         if name in ('return', 'returns'):
             continue
         if name in has_description and name not in has_type:
+            # Use short form if autodoc_unqualified_typehints is enabled
+            if app.config.autodoc_unqualified_typehints:
+                annotation = typing.stringify(annotation, short=True)
             field = nodes.field()
             field += nodes.field_name('', 'type ' + name)
             field += nodes.field_body('', nodes.paragraph('', annotations[name]))
"""

TOX_PATCH = """diff --git a/tox.ini b/tox.ini
index c006fa5a6..e51fa8598 100644
--- a/tox.ini
+++ b/tox.ini
@@ -28,7 +28,7 @@ setenv =
     PYTHONWARNINGS = all,ignore::ImportWarning:importlib._bootstrap_external,ignore::DeprecationWarning:site,ignore::DeprecationWarning:distutils,ignore::DeprecationWarning:pip._vendor.packaging.version
     PYTEST_ADDOPTS = {env:PYTEST_ADDOPTS:} --color yes
 commands=
-    python -X dev -m pytest --durations 25 {posargs}
+    python -X dev -m pytest -rA --durations 25 {posargs}
 
 [testenv:du-latest]
 commands =
"""

NDIM_ARRAY_PATCH = """diff --git a/sympy/tensor/array/ndim_array.py b/sympy/tensor/array/ndim_array.py
index 6490a655a4..5b88a15a24 100644
--- a/sympy/tensor/array/ndim_array.py
+++ b/sympy/tensor/array/ndim_array.py
@@ -194,6 +194,9 @@ def f(pointer):
             if not isinstance(pointer, Iterable):
                 return [pointer], ()
 
+            if not pointer:  # Detect empty iterable
+                return [], ()
+
             result = []
             elems, shapes = zip(*[f(i) for i in pointer])
             if len(set(shapes)) != 1:
@@ -210,7 +213,7 @@ def _handle_ndarray_creation_inputs(cls, iterable=None, shape=None, **kwargs):
         from sympy.tensor.array import SparseNDimArray
 
         if shape is None:
-            if iterable is None:
+            if iterable is None or (isinstance(iterable, Iterable) and not iterable):
                 shape = ()
                 iterable = ()
             # Construction of a sparse array from a sparse array
"""


def test_clean_from_end():
    patch = "\n".join([TYPEHINTS_PATCH, TOX_PATCH])
    # Requires a slight fixup, but I guess it's OK
    assert clean_patch(patch) == "\n".join([TYPEHINTS_PATCH, ""])


def test_clean_from_middle():
    patch = "\n".join([TYPEHINTS_PATCH, TOX_PATCH, NDIM_ARRAY_PATCH])
    assert clean_patch(patch) == "\n".join([TYPEHINTS_PATCH, NDIM_ARRAY_PATCH])


def test_clean_multiple():
    patch = "\n".join([TYPEHINTS_PATCH, SETUP_PATCH, TOX_PATCH, NDIM_ARRAY_PATCH])
    assert clean_patch(patch) == "\n".join([TYPEHINTS_PATCH, NDIM_ARRAY_PATCH])


def test_clean_from_start():
    patch = "\n".join([TOX_PATCH, TYPEHINTS_PATCH])
    assert clean_patch(patch) == TYPEHINTS_PATCH


def test_clean_nop():
    patch = "\n".join([TYPEHINTS_PATCH, NDIM_ARRAY_PATCH])
    assert clean_patch(patch) == "\n".join([TYPEHINTS_PATCH, NDIM_ARRAY_PATCH])
