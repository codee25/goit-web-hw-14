import os
import sys

# Додаємо шлях до кореня проєкту (два рівні вгору від docs/source/)
# Це дозволить Sphinx імпортувати твої модулі auth, main тощо
sys.path.insert(0, os.path.abspath('../../'))

project = 'FastApiproject'
copyright = '2026, Vla'
author = 'Vla'

# Додаємо необхідні розширення
extensions = [
    'sphinx.ext.autodoc',  # Для автоматичного збору docstrings
    'sphinx.ext.napoleon', # Для підтримки стилів Google та NumPy (опціонально)
]

templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

# Змінюємо тему на більш читабельну (наприклад, nature)
html_theme = 'nature'

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'alabaster'
html_static_path = ['_static']
