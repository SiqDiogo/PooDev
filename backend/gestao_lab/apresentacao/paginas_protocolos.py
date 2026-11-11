from html import escape

from . import paginas
from ..dominio.usuarios import ChefeLaboratorio


def _data(instante):
    return instante.strftime("%d/%m/%Y %H:%M") if instante else "—"


def lista(usuario, csrf, protocolos, mensagem=""):
    linhas = []
    for protocolo in protocolos:
        estado = "Validado" if protocolo.validado else (
            "Aguardando validação" if protocolo.assinado else "Aguardando assinatura"
        )
        linhas.append(
            f'<tr><td><a href="/protocolos/detalhe?id={protocolo.id}">'
            f'{escape(protocolo.titulo)}</a></td>'
            f'<td>{escape(protocolo.autor_nome)}</td><td>{escape(estado)}</td>'
            f'<td>{_data(protocolo.criado_em)}</td>'
            f'<td><a href="/protocolos/download?id={protocolo.id}">Baixar PDF</a></td></tr>'
        )
    corpo = paginas.aviso(mensagem) + '''
        <p>Os protocolos são compartilhados entre os usuários do mesmo laboratório.
        O autor assina o documento e o Chefe confirma sua validação.</p>
        <div class="acoes"><a class="botao" href="/protocolos/novo">Adicionar protocolo</a></div>
        <div class="tabela"><table><thead><tr>
            <th>Título</th><th>Autor</th><th>Situação</th><th>Cadastro</th><th>Arquivo</th>
        </tr></thead><tbody>''' + (
            "".join(linhas) if linhas else '<tr><td colspan="5">Nenhum protocolo cadastrado.</td></tr>'
        ) + "</tbody></table></div>"
    return paginas.layout("Protocolos", corpo, usuario, csrf)


def novo(usuario, csrf, mensagem="", titulo=""):
    corpo = paginas.aviso(mensagem, True) + f'''
        <section class="cartao">
            <p>O arquivo original será mantido. Tamanho máximo: 5 MB.
            A assinatura do autor será registrada após o cadastro.</p>
            <form method="post" action="/protocolos/novo" enctype="multipart/form-data">
                {paginas.oculto(csrf)}
                {paginas.campo("titulo", "Título", titulo, limite=180)}
                <label>Arquivo PDF
                    <input type="file" name="arquivo" accept=".pdf,application/pdf" required>
                </label>
                <div class="acoes"><button>Adicionar protocolo</button>
                <a href="/protocolos">Cancelar</a></div>
            </form>
        </section>'''
    return paginas.layout("Adicionar protocolo", corpo, usuario, csrf)


def detalhe(usuario, csrf, protocolo, equipamentos, mensagem=""):
    status = "Validado" if protocolo.validado else (
        "Assinado; aguardando validação" if protocolo.assinado else "Não assinado"
    )
    linhas = [
        ("Autor", protocolo.autor_nome),
        ("Arquivo", protocolo.nome_arquivo),
        ("Cadastro", _data(protocolo.criado_em)),
        ("Assinatura", _data(protocolo.assinado_em)),
        ("Validação", _data(protocolo.validado_em)),
        ("Situação", status),
    ]
    detalhes = "".join(
        f"<dt>{escape(nome)}</dt><dd>{escape(str(valor))}</dd>"
        for nome, valor in linhas
    )
    corpo = paginas.aviso(mensagem) + f'''
        <section class="cartao">
            <h2>{escape(protocolo.titulo)}</h2>
            <dl>{detalhes}</dl>
            <div class="acoes"><a class="botao secundario"
                href="/protocolos/download?id={protocolo.id}">Baixar PDF original</a>
                <a href="/protocolos">Voltar</a></div>
        </section>'''
    if usuario.id == protocolo.autor_id and not protocolo.assinado:
        corpo += f'''<section class="cartao">
            <p>Ao confirmar, você registra sua autoria e bloqueia alterações no documento.
            Esta assinatura é um registro autenticado no sistema, não um certificado digital.</p>
            <form method="post" action="/protocolos/assinar">
                {paginas.oculto(csrf)}
                <input type="hidden" name="protocolo_id" value="{protocolo.id}">
                <button>Assinar como autor</button>
            </form>
        </section>'''
    if isinstance(usuario, ChefeLaboratorio) and protocolo.assinado and not protocolo.validado:
        corpo += f'''<section class="cartao">
            <p>Confirme a validação após revisar o documento assinado.</p>
            <form method="post" action="/protocolos/validar">
                {paginas.oculto(csrf)}
                <input type="hidden" name="protocolo_id" value="{protocolo.id}">
                <button>Validar protocolo</button>
            </form>
        </section>'''
    vinculos = "".join(
        f"<li>{escape(v.nome)} ({escape(v.patrimonio)})</li>"
        for v in protocolo.vinculos
    ) or "<li>Nenhum equipamento vinculado.</li>"
    corpo += f'<section class="cartao"><h2>Equipamentos vinculados</h2><ul>{vinculos}</ul>'
    if isinstance(usuario, ChefeLaboratorio) and protocolo.validado:
        vinculados = {v.equipamento_id for v in protocolo.vinculos}
        opcoes = "".join(
            f'<option value="{e.id}">{escape(e.nome)}'
            f' ({escape(e.numero_patrimonio)})</option>'
            for e in equipamentos if e.id not in vinculados
        )
        if opcoes:
            corpo += f'''<form method="post" action="/protocolos/vincular">
                {paginas.oculto(csrf)}
                <input type="hidden" name="protocolo_id" value="{protocolo.id}">
                <label>Vincular a outro equipamento
                    <select name="equipamento_id" required>
                        <option value="">Selecione um equipamento</option>{opcoes}
                    </select>
                </label>
                <button>Vincular equipamento</button>
            </form>'''
    corpo += "</section>"
    return paginas.layout("Detalhes do protocolo", corpo, usuario, csrf)
