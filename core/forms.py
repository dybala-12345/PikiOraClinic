"""Form helpers shared by every app."""

from django import forms


class BootstrapFormMixin:
    """
    Adds Bootstrap 5 CSS classes to every widget so templates stay simple
    and all forms look consistent.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, (forms.CheckboxInput, forms.CheckboxSelectMultiple)):
                css = "form-check-input"
            elif isinstance(widget, (forms.Select, forms.SelectMultiple)):
                css = "form-select"
            else:
                css = "form-control"
            existing = widget.attrs.get("class", "")
            widget.attrs["class"] = f"{existing} {css}".strip()


class DateInput(forms.DateInput):
    """HTML5 date picker."""

    input_type = "date"

    def __init__(self, attrs=None, format="%Y-%m-%d"):
        super().__init__(attrs=attrs, format=format)


class TimeInput(forms.TimeInput):
    """HTML5 time picker."""

    input_type = "time"

    def __init__(self, attrs=None, format="%H:%M"):
        super().__init__(attrs=attrs, format=format)
