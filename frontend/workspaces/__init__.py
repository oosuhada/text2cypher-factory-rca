"""Official internal-console workspace module boundary.

Streamlit reserves a sibling ``pages`` directory for automatic multipage
navigation.  The application imports workspace renderers through this package
so product code does not depend on that framework-reserved namespace.
"""
