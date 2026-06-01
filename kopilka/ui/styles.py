"""Custom CSS styles."""

CSS = """
.card {
    border: 1px solid @borders;
    border-radius: 8px;
    padding: 15px;
    background-color: @view_bg_color;
}

.title-1 {
    font-size: 28px;
    font-weight: bold;
}

.title-2 {
    font-size: 18px;
    font-weight: bold;
}
"""


def load_styles(app):
    """Load custom styles into the application."""
    css_provider = app.get_css_provider()
    css_provider.load_from_data(CSS.encode())
