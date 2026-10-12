from django import forms


class BootstrapFormMixin:
    """Adds Bootstrap classes to every widget of a form."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault('class', 'form-check-input')
            elif isinstance(widget, (forms.Select, forms.SelectMultiple)):
                widget.attrs.setdefault('class', 'form-select')
            else:
                widget.attrs.setdefault('class', 'form-control')


class BootstrapForm(BootstrapFormMixin, forms.Form):
    pass


class BootstrapModelForm(BootstrapFormMixin, forms.ModelForm):
    pass
