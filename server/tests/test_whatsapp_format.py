"""Formatação das mensagens enviadas ao WhatsApp.

O WhatsApp usa `*negrito*` com um asterisco. O modelo escreve Markdown por
hábito, e `**360**` chegou ao passageiro com os asteriscos visíveis numa
conversa real.
"""

import pytest

from app.utils.whatsapp_format import to_whatsapp


class TestBold:
    def test_markdown_bold_becomes_whatsapp_bold(self):
        assert to_whatsapp("Pega o **360** na parada") == "Pega o *360* na parada"

    def test_underscore_bold_becomes_whatsapp_bold(self):
        assert to_whatsapp("Pega o __360__ ali") == "Pega o *360* ali"

    def test_already_correct_bold_is_left_alone(self):
        assert to_whatsapp("Pega o *360* na parada") == "Pega o *360* na parada"

    def test_several_bolds_in_one_message(self):
        texto = "Pega o **360** ou o **042** hoje"

        assert to_whatsapp(texto) == "Pega o *360* ou o *042* hoje"

    def test_bold_does_not_swallow_across_lines(self):
        """Um asterisco solto não pode transformar o resto da mensagem."""
        texto = "linha **360**\noutra coisa ** aqui"

        resultado = to_whatsapp(texto)

        assert resultado.startswith("linha *360*")
        assert "outra coisa" in resultado

    def test_a_lone_asterisk_is_untouched(self):
        assert to_whatsapp("2 * 3 = 6") == "2 * 3 = 6"


class TestOtherMarkdown:
    def test_headings_become_bold(self):
        assert to_whatsapp("## Opções de viagem") == "*Opções de viagem*"

    def test_trailing_spaces_are_stripped(self):
        """Markdown quebra linha com dois espaços; no WhatsApp é só sujeira."""
        assert to_whatsapp("primeira linha  \nsegunda") == "primeira linha\nsegunda"

    def test_emoji_and_accents_survive(self):
        texto = "Passa às 16:58, daqui a 7 minutos 🚌 na Avenida São Paulo 📍"

        assert to_whatsapp(texto) == texto


class TestEdgeCases:
    @pytest.mark.parametrize("valor", ["", None])
    def test_empty_input_is_returned_as_is(self, valor):
        assert to_whatsapp(valor) == valor

    def test_a_real_message_from_the_logs(self):
        """Mensagem exata que saiu com os asteriscos visíveis."""
        original = (
            "Pega o **360** na parada em frente ao nº 585 da Avenida São Paulo 📍  \n"
            "Passa às 16:58, daqui a 7 minutos · chega ao Shopping Recife às 17:19 🚌"
        )

        resultado = to_whatsapp(original)

        assert "**" not in resultado
        assert "*360*" in resultado
        assert resultado.endswith("17:19 🚌")
