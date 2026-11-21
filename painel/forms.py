from django import forms
from django.contrib.auth.forms import AuthenticationForm, UsernameField

from painel.html_seguro import sanitizar, texto_puro
from painel.models import Equipe, MotivoOcorrencia, Ocorrencia, SetorOcorrencia


class EntrarForm(AuthenticationForm):
    username = UsernameField(
        label="Usuário",
        widget=forms.TextInput(attrs={"autofocus": True, "autocomplete": "username"}),
    )
    password = forms.CharField(
        label="Senha",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )
    error_messages = {
        "invalid_login": "Usuário ou senha incorretos.",
        "inactive": "Esta conta está inativa.",
    }


class OcorrenciaForm(forms.Form):
    use_required_attribute = False
    equipe = forms.ModelChoiceField(queryset=Equipe.objects.none(), required=False, label="Equipe")
    numero_nota = forms.CharField(label="Nota fiscal", max_length=32)
    cliente = forms.CharField(label="Nome do cliente", max_length=160)
    peso = forms.CharField(label="Peso (kg)")
    valor = forms.CharField(label="Valor")
    tipo_devolucao = forms.ChoiceField(
        label="Tipo de devolução", choices=Ocorrencia.TipoDevolucao.choices
    )
    placa = forms.CharField(label="Placa do veículo", required=False, max_length=12)
    setor = forms.ModelChoiceField(
        queryset=SetorOcorrencia.objects.none(),
        label="Setor responsável",
        empty_label="Selecione o setor",
    )
    motivo = forms.ModelChoiceField(
        queryset=MotivoOcorrencia.objects.none(),
        label="Motivo",
        empty_label="Selecione o motivo",
    )
    descricao = forms.CharField(
        label="Descrição",
        max_length=20000,
        widget=forms.Textarea(attrs={"rows": 6, "class": "editor-fonte"}),
        error_messages={"required": "Descreva o que aconteceu."},
    )
    produtos_json = forms.CharField(required=False, widget=forms.HiddenInput)

    def __init__(self, *args, equipes=None, fixar_equipe=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["equipe"].queryset = equipes if equipes is not None else Equipe.objects.all()
        self.fields["equipe"].empty_label = "Selecione a equipe"
        self.fields["setor"].queryset = SetorOcorrencia.objects.filter(ativo=True)
        self.fields["motivo"].queryset = MotivoOcorrencia.objects.filter(ativo=True)
        if fixar_equipe:
            del self.fields["equipe"]
        for nome, campo in self.fields.items():
            if isinstance(campo.widget, forms.HiddenInput):
                continue
            css = "input textarea" if isinstance(campo.widget, forms.Textarea) else "input"
            campo.widget.attrs.setdefault("class", css)
            campo.error_messages.setdefault("required", "Preencha este campo.")
        self.fields["numero_nota"].widget.attrs.update(
            {
                "autocomplete": "off",
                "placeholder": "Nº NF",
                "inputmode": "numeric",
                "class": "input input-nota",
            }
        )
        self.fields["cliente"].widget.attrs["placeholder"] = "Quem recebeu a carga"
        self.fields["peso"].widget.attrs["placeholder"] = "0,000"
        self.fields["valor"].widget.attrs["placeholder"] = "0,00"
        self.fields["placa"].widget.attrs["placeholder"] = "ABC1D23"
        self.fields["descricao"].widget.attrs.update(
            {
                "class": "editor-fonte",
                "tabindex": "-1",
                "placeholder": "O que aconteceu, onde, e o que o cliente recusou.",
            }
        )

    def clean_descricao(self):
        html = sanitizar(self.cleaned_data.get("descricao") or "")
        if len(texto_puro(html)) < 10:
            raise forms.ValidationError("Descreva a ocorrência com pelo menos 10 caracteres.")
        return html


class ComplementoForm(forms.Form):
    texto = forms.CharField(
        label="Complemento",
        min_length=3,
        max_length=4000,
        widget=forms.Textarea(
            attrs={
                "rows": 4,
                "class": "input textarea",
                "placeholder": "O que mudou agora, sem apagar o lançamento original.",
            }
        ),
        error_messages={"required": "Escreva o complemento.", "min_length": "Mínimo de 3 caracteres."},
    )
