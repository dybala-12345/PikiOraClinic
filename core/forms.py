from django import forms


class BootstrapFormMixin:
    # adds bootstrap classes to all form fields so every form looks the same

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
    # date picker

    input_type = "date"

    def __init__(self, attrs=None, format="%Y-%m-%d"):
        super().__init__(attrs=attrs, format=format)


class TimeInput(forms.TimeInput):
    # time picker

    input_type = "time"

    def __init__(self, attrs=None, format="%H:%M"):
        super().__init__(attrs=attrs, format=format)
