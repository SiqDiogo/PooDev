from html import escape
from datetime import datetime, timedelta, timezone
from ..dominio.usuarios import Aluno, ChefeLaboratorio, Perfil, Professor, TipoAluno

ROTULOS = {Perfil.ALUNO: "Aluno", Perfil.PROFESSOR: "Professor", Perfil.CHEFE: "Chefe de Laboratório"}
CATEGORIAS = {TipoAluno.GRADUACAO: "Graduação", TipoAluno.MESTRADO: "Mestrado",
              TipoAluno.DOUTORADO: "Doutorado", TipoAluno.POS: "Pós"}


def oculto(csrf):
    return f'<input type="hidden" name="csrf" value="{escape(csrf, quote=True)}">'


def layout(titulo, conteudo, usuario=None, csrf=""):
    nav = ''
    if usuario:
        links = (
            '<a href="/">Meu perfil</a>'
            '<a href="/reservas/nova">Reservar</a>'
        )

        links += '<a href="/reservas">Reservas</a>'
        links += '<a href="/historico">Histórico</a>'
        links += '<a href="/chaves">Chaves</a><a href="/recursos">Recursos</a>'

        if isinstance(usuario, ChefeLaboratorio):
            links += (
                '<a href="/usuarios">Usuários</a>'
                '<a href="/cadastros/aluno">Cadastrar aluno</a>'
                '<a href="/cadastros/professor">Cadastrar professor</a>'
                '<a href="/limites-reserva">Limites</a>'
            )

        nav = f'<nav>{links}<form method="post" action="/sair">{oculto(csrf)}<button class="secundario">Sair</button></form></nav>'
    return f'''<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(titulo)} · Gestão de Laboratório</title><link rel="stylesheet" href="/estilo.css"></head>
<body><header><a class="marca" href="/">Gestão de Laboratório</a>{nav}</header>
<main><h1>{escape(titulo)}</h1>{conteudo}</main></body></html>'''


def aviso(mensagem, erro=False):
    return f'<p class="aviso {"erro" if erro else "sucesso"}" role="alert">{escape(mensagem)}</p>' if mensagem else ''


def campo(nome, rotulo, valor="", tipo="text", obrigatorio=True, limite=120, autocomplete=None):
    obrigacao = " required" if obrigatorio else ""
    completar = f' autocomplete="{autocomplete}"' if autocomplete else ''
    minimo = ' minlength="12"' if tipo == "password" and autocomplete == "new-password" else ''
    return f'<label>{escape(rotulo)}<input name="{nome}" type="{tipo}" value="{escape(str(valor), quote=True)}" maxlength="{limite}"{obrigacao}{completar}{minimo}></label>'


def login(csrf, mensagem="", email=""):
    conteudo = aviso(mensagem, True) + f'''<section class="cartao estreito"><p>Entre com sua conta para acessar o laboratório.</p>
<form method="post" action="/entrar">{oculto(csrf)}
{campo("email", "E-mail", email, "email", limite=254, autocomplete="username")}
{campo("senha", "Senha", tipo="password", limite=128, autocomplete="current-password")}
<button>Entrar</button></form></section>'''
    return layout("Entrar", conteudo)


def perfil(usuario, csrf):
    dados = [("Nome", usuario.nome), ("E-mail", usuario.email), ("Perfil", ROTULOS[usuario.perfil])]
    if isinstance(usuario, Professor):
        dados += [("Programa de pós", usuario.programa_pos), ("Ramal", usuario.ramal or "Não informado")]
    if isinstance(usuario, Aluno):
        dados += [("Matrícula", usuario.matricula), ("Categoria", CATEGORIAS[usuario.tipo])]
    detalhes = ''.join(f'<dt>{escape(k)}</dt><dd>{escape(str(v))}</dd>' for k, v in dados)
    acao = '<a class="botao" href="/usuarios">Gerenciar usuários</a>' if isinstance(usuario, ChefeLaboratorio) else ''
    return layout("Meu perfil", f'<section class="cartao"><dl>{detalhes}</dl>{acao}</section>', usuario, csrf)


def usuarios(lista, ator, csrf, mensagem=""):
    linhas = []

    for u in lista:
        detalhe = (
            f'Matrícula: {u.matricula}'
            if isinstance(u, Aluno)
            else u.programa_pos
        )

        acao = (
            f'<a class="botao secundario" '
            f'href="/usuarios/remover?id={u.id}">'
            f'Remover cadastro</a>'
            if u.ativo and not isinstance(u, ChefeLaboratorio)
            else '—'
        )

        linhas.append(
            f'<tr>'
            f'<td>{escape(u.nome)}</td>'
            f'<td>{escape(u.email)}</td>'
            f'<td>{ROTULOS[u.perfil]}</td>'
            f'<td>{escape(detalhe)}</td>'
            f'<td>{"Ativo" if u.ativo else "Inativo"}</td>'
            f'<td>{acao}</td>'
            f'</tr>'
        )

    corpo = aviso(mensagem) + f'''
    <p>Contas vinculadas ao seu laboratório.
    A remoção desativa o acesso e preserva o histórico.</p>

    <div class="acoes">
        <a class="botao" href="/cadastros/aluno">
            Cadastrar aluno
        </a>
        <a class="botao secundario" href="/cadastros/professor">
            Cadastrar professor
        </a>
    </div>

    <div class="tabela">
        <table>
            <thead>
                <tr>
                    <th>Nome</th>
                    <th>E-mail</th>
                    <th>Perfil</th>
                    <th>Dados acadêmicos</th>
                    <th>Situação</th>
                    <th>Ação</th>
                </tr>
            </thead>
            <tbody>{''.join(linhas)}</tbody>
        </table>
    </div>'''

    return layout("Usuários", corpo, ator, csrf)


def cadastro(perfil_cadastro, ator, csrf, orientadores, dados=None, mensagem=""):
    dados = dados or {}
    corpo = aviso(mensagem, True) + '<section class="cartao"><p>O cadastro será vinculado ao seu laboratório.</p>'
    rota = "aluno" if perfil_cadastro == Perfil.ALUNO else "professor"
    corpo += f'<form method="post" action="/cadastros/{rota}">{oculto(csrf)}<div class="campos">'
    corpo += campo("nome", "Nome completo", dados.get("nome", ""), autocomplete="name")
    corpo += campo("email", "E-mail", dados.get("email", ""), "email", limite=254, autocomplete="email")
    if perfil_cadastro == Perfil.ALUNO:
        corpo += campo("matricula", "Matrícula", dados.get("matricula", ""), limite=64)
        opcoes = ''.join(f'<option value="{t.value}"{" selected" if dados.get("tipo", "GRADUACAO") == t.value else ""}>{CATEGORIAS[t]}</option>' for t in TipoAluno)
        corpo += f'<label>Categoria<select name="tipo" required>{opcoes}</select></label>'
        opcoes = '<option value="">Selecione um orientador</option>' + ''.join(
            f'<option value="{p.id}"{" selected" if str(dados.get("orientador_id", "")) == str(p.id) else ""}>{escape(p.nome)}</option>' for p in orientadores)
        corpo += f'<label>Orientador<select name="orientador_id" required>{opcoes}</select></label>'
    else:
        corpo += campo("programa_pos", "Programa de pós", dados.get("programa_pos", ""))
        corpo += campo("ramal", "Ramal", dados.get("ramal", ""), obrigatorio=False, limite=40)
    # Nunca devolvemos a senha em um formulário que apresentou erro.
    corpo += campo("senha", "Senha inicial (12 a 128 caracteres)", tipo="password", limite=128, autocomplete="new-password")
    corpo += campo("confirmacao", "Confirmar senha", tipo="password", limite=128, autocomplete="new-password")
    corpo += '</div><div class="acoes"><button>Cadastrar</button><a href="/usuarios">Voltar</a></div></form></section>'
    titulo = "Cadastrar aluno" if perfil_cadastro == Perfil.ALUNO else "Cadastrar professor"
    return layout(titulo, corpo, ator, csrf)


def confirmar_remocao(alvo, ator, csrf):
    nome = escape(alvo.nome)
    email = escape(alvo.email)

    conteudo = f'''
    <section class="cartao estreito">
        <p>
            Deseja remover o cadastro de
            <strong>{nome}</strong> ({email})?
        </p>

        <p>
            O acesso será desativado e as sessões abertas
            serão encerradas. Os registros históricos
            serão preservados.
        </p>

        <form method="post" action="/usuarios/remover">
            {oculto(csrf)}

            <input
                type="hidden"
                name="usuario_id"
                value="{alvo.id}"
            >

            <div class="acoes">
                <button>Confirmar remoção</button>
                <a href="/usuarios">Cancelar</a>
            </div>
        </form>
    </section>
    '''

    return layout(
        "Confirmar remoção de cadastro",
        conteudo,
        ator,
        csrf
    )


def _selecao_recurso(
    nome, rotulo, opcoes, selecionado="", obrigatorio=True
):
    itens = ['<option value="">Selecione...</option>']

    for identificador, descricao in opcoes:
        valor = str(identificador)
        marcado = (
            ' selected'
            if str(selecionado) == valor
            else ''
        )

        itens.append(
            f'<option value="{escape(valor, quote=True)}"{marcado}>'
            f'{escape(str(descricao))}</option>'
        )

    atributo = ' required' if obrigatorio else ''

    return (
        f'<label>{escape(rotulo)}'
        f'<select name="{escape(nome, quote=True)}"{atributo}>'
        f'{"".join(itens)}</select></label>'
    )



def _pagina_cadastro_recurso(
    titulo, rota, campos_html, ator, csrf,
    mensagem="", instrucao=""
):
    corpo = aviso(mensagem, True)
    corpo += '<section class="cartao">'

    corpo += (
        '<p>O recurso será vinculado ao laboratório '
        'do Chefe autenticado.</p>'
    )

    if instrucao:
        corpo += f'<p>{escape(instrucao)}</p>'

    corpo += (
        f'<form method="post" action="{rota}">'
        f'{oculto(csrf)}'
        f'<div class="campos">{campos_html}</div>'
        '<div class="acoes">'
        '<button type="submit">Cadastrar</button>'
        '<a href="/recursos">Voltar</a>'
        '</div></form></section>'
    )

    return layout(titulo, corpo, ator, csrf)



def formulario_sala(ator, csrf, dados=None, mensagem="", responsaveis=None):
    dados = dados or {}

    campos = (
        campo(
            "nome", "Nome da sala",
            dados.get("nome", "")
        )
        + campo(
            "identificacao", "Identificação",
            dados.get("identificacao", ""), limite=80
        )
        + campo(
            "localizacao", "Localização",
            dados.get("localizacao", ""), limite=200
        )
        + campo(
            "capacidade", "Capacidade (pessoas)",
            dados.get("capacidade", ""),
            tipo="number", limite=9
        )
    )

    return _pagina_cadastro_recurso(
        "Cadastrar sala",
        "/cadastros/sala",
        campos + _selecao_responsavel(ator, dados, responsaveis), ator, csrf, mensagem
    )



def formulario_bancada(
    ator, csrf, salas, dados=None, mensagem="", responsaveis=None
):
    dados = dados or {}

    opcoes = [
        (s.id, f"{s.identificacao} — {s.nome}")
        for s in salas if s.id is not None
    ]

    campos = (
        campo(
            "nome", "Nome da bancada",
            dados.get("nome", "")
        )
        + campo(
            "numero_identificacao",
            "Identificação da bancada",
            dados.get("numero_identificacao", ""),
            limite=80
        )
        + _selecao_recurso(
            "sala_id",
            "Sala",
            opcoes,
            dados.get("sala_id", "")
        )
    )

    return _pagina_cadastro_recurso(
        "Cadastrar bancada",
        "/cadastros/bancada",
        campos + _selecao_responsavel(ator, dados, responsaveis), ator, csrf, mensagem
    )




def formulario_equipamento(
    ator, csrf, salas, bancadas, dados=None, mensagem="", responsaveis=None
):
    dados = dados or {}

    opcoes_salas = [
        (s.id, f"{s.identificacao} — {s.nome}")
        for s in salas if s.id is not None
    ]

    opcoes_bancadas = [
        (b.id, f"{b.numero_identificacao} — {b.nome}")
        for b in bancadas if b.id is not None
    ]

    campos = (
        campo(
            "nome", "Nome do equipamento",
            dados.get("nome", "")
        )
        + campo(
            "numero_patrimonio", "Número de patrimônio",
            dados.get("numero_patrimonio", ""), limite=80
        )
        + campo(
            "complemento_local", "Complemento do local",
            dados.get("complemento_local", ""), limite=200
        )
        + _selecao_recurso(
            "bancada_id", "Bancada (opcional)",
            opcoes_bancadas, dados.get("bancada_id", ""),
            False
        )
        + _selecao_recurso(
            "sala_direta_id", "Sala direta (opcional)",
            opcoes_salas, dados.get("sala_direta_id", ""),
            False
        )
        + campo(
            "foto_uri", "Endereço da foto (opcional)",
            dados.get("foto_uri", ""),
            obrigatorio=False, limite=500
        )
        + campo(
            "observacao", "Observação (opcional)",
            dados.get("observacao", ""),
            obrigatorio=False, limite=500
        )
    )

    return _pagina_cadastro_recurso(
        "Cadastrar equipamento",
        "/cadastros/equipamento",
        campos + _selecao_responsavel(ator, dados, responsaveis), ator, csrf, mensagem,
        instrucao=(
            "Selecione uma bancada OU uma sala direta, "
            "nunca ambas."
        )
    )



def _lista_visual_recursos(itens):
    if not itens:
        return "<p>Nenhum recurso cadastrado.</p>"

    linhas = "".join(
        f"<li>{escape(str(item))}</li>"
        for item in itens
    )

    return f"<ul>{linhas}</ul>"


def painel_recursos(
    ator, csrf, salas, bancadas, equipamentos, mensagem=""
):
    descricoes_salas = [
        f"{s.identificacao} — {s.nome} "
        f"(capacidade: {s.capacidade})"
        for s in salas
    ]

    descricoes_bancadas = [
        f"{b.numero_identificacao} — {b.nome}"
        for b in bancadas
    ]

    salas_por_id = {s.id: s for s in salas}
    bancadas_por_id = {b.id: b for b in bancadas}
    descricoes_equipamentos = []
    for equipamento in equipamentos:
        bancada = bancadas_por_id.get(equipamento.bancada_id)
        sala = salas_por_id[bancada.sala_id if bancada else equipamento.sala_direta_id]
        destino = f"sala {sala.identificacao}"
        destino += f" / bancada {bancada.numero_identificacao}" if bancada else " / diretamente na sala"
        descricoes_equipamentos.append(
            f"{equipamento.numero_patrimonio} — {equipamento.nome} — {sala.localizacao} / {destino} / {equipamento.complemento_local}"
        )

    corpo = aviso(mensagem)

    if isinstance(ator, ChefeLaboratorio):
        corpo += '''
    <section class="cartao">
        <h2>Gerenciar recursos</h2><p><a href="/recursos/vinculos">Vínculos de equipamentos</a></p>
        <p>Cadastre e consulte os recursos do laboratório.</p>

        <div class="acoes">
            <a class="botao" href="/cadastros/sala">
                Cadastrar sala
            </a>
            <a class="botao secundario" href="/cadastros/bancada">
                Cadastrar bancada
            </a>
            <a class="botao secundario" href="/cadastros/equipamento">
                Cadastrar equipamento
            </a>
        </div>
    </section>
    '''

    corpo += (
        '<section class="cartao"><h2>Salas</h2>'
        + _lista_visual_recursos(descricoes_salas)
        + '</section>'
    )

    corpo += (
        '<section class="cartao"><h2>Bancadas</h2>'
        + _lista_visual_recursos(descricoes_bancadas)
        + '</section>'
    )

    corpo += (
        '<section class="cartao"><h2>Equipamentos</h2>'
        + ('<ul>' + ''.join(f'<li>{escape(descricao)}'
             + (f' — <a href="/recursos/localizacao?id={e.id}">Alterar localização</a>' if isinstance(ator, ChefeLaboratorio) else '')
             + '</li>' for e, descricao in zip(equipamentos, descricoes_equipamentos)) + '</ul>'
           if equipamentos else '<p>Nenhum equipamento cadastrado.</p>')
        + '</section>'
    )

    return layout("Recursos do laboratório", corpo, ator, csrf)




def formulario_reserva(
    ator,
    csrf,
    salas,
    bancadas,
    equipamentos,
    dados=None,
    mensagem="",
    sucesso="",
    disponibilidade=None
):
    dados = dados or {}

    # Organiza as opções do formulário.
    opcoes = (
        [
            (
                sala.id,
                f"Sala — {sala.identificacao} — "
                f"{sala.nome} ({sala.estado.value})"
            )
            for sala in salas
            if sala.id is not None
        ]
        +
        [
            (
                bancada.id,
                f"Bancada — {bancada.numero_identificacao} — "
                f"{bancada.nome} ({bancada.estado.value})"
            )
            for bancada in bancadas
            if bancada.id is not None
        ]
        +
        [
            (
                equipamento.id,
                f"Equipamento — {equipamento.numero_patrimonio} — "
                f"{equipamento.nome} ({equipamento.estado.value})"
            )
            for equipamento in equipamentos
            if equipamento.id is not None
        ]
    )

    # Campos que o usuário preencherá.
    campos = (
        _selecao_recurso(
            "recurso_id",
            "Recurso",
            opcoes,
            dados.get("recurso_id", "")
        )
        + campo(
            "inicio",
            "Início (horário de Brasília, UTC-03:00)",
            dados.get("inicio", ""),
            "datetime-local"
        )
        + campo(
            "fim",
            "Fim (horário de Brasília, UTC-03:00)",
            dados.get("fim", ""),
            "datetime-local"
        )
    )

    corpo = aviso(sucesso) + aviso(mensagem, True)
    if disponibilidade is not None:
        linhas = ''.join(f'<tr><td>{escape(r["nome"])}</td><td>{escape(r["local"])}</td><td>{"Disponível" if r["livre"] else "Indisponível no período ou para seu perfil"}</td></tr>' for r in disponibilidade)
        corpo += '<section class="cartao"><h2>Disponibilidade no período</h2><div class="tabela"><table><thead><tr><th>Recurso</th><th>Local</th><th>Situação</th></tr></thead><tbody>' + linhas + '</tbody></table></div></section>'

    corpo += (
        '<section class="cartao">'
        '<p>Reservar uma bancada inclui todos os '
        'equipamentos nela. Reservar uma sala '
        'bloqueia a sala inteira durante o período '
        'escolhido.</p>'
        '<form method="get" action="/reservas/nova"><div class="campos">'
        + campo("inicio", "Consultar desde (Brasília)", dados.get("inicio", ""), "datetime-local")
        + campo("fim", "Consultar até (Brasília)", dados.get("fim", ""), "datetime-local")
        + '</div><button>Consultar disponibilidade</button></form></section><section class="cartao">'
        '<form method="post" action="/reservas/nova">'
        + oculto(csrf)
        + f'<div class="campos">{campos}</div>'
        + '<div class="acoes">'
        '<button type="submit">Confirmar reserva</button>'
        '<a href="/">Voltar</a>'
        '</div></form></section>'
    )

    return layout(
        "Reservar recurso",
        corpo,
        ator,
        csrf
    )




def pagina_reservas(
    ator,
    csrf,
    reservas,
    mensagem="",
    erro=False
):
    eh_chefe = isinstance(ator, ChefeLaboratorio)

    titulo = (
        "Reservas do laboratório"
        if eh_chefe
        else "Minhas reservas"
    )

    corpo = aviso(mensagem, erro)

    corpo += (
        '<section class="cartao">'
        '<p>Consulte as reservas registradas e '
        'cancele as que não serão utilizadas.</p>'
        '<div class="acoes">'
        '<a class="botao" href="/reservas/nova">'
        'Nova reserva</a>'
        '</div>'
        '</section>'
    )

    if not reservas:
        corpo += (
            '<section class="cartao">'
            '<p>Nenhuma reserva encontrada.</p>'
            '</section>'
        )

        return layout(titulo, corpo, ator, csrf)

    fuso = timezone(timedelta(hours=-3))
    linhas = []

    for reserva in reservas:
        inicio = reserva["inicio"].astimezone(fuso)
        fim = reserva["fim"].astimezone(fuso)

        periodo = (
            f'{inicio:%d/%m/%Y %H:%M} até '
            f'{fim:%d/%m/%Y %H:%M}'
        )

        estado = reserva["estado"]

        rotulos = {
            "CONFIRMADA": "Confirmada",
            "CANCELADA": "Cancelada",
            "CONCLUIDA": "Concluída"
        }

        situacao = rotulos.get(
            estado, estado
        )
        if estado == "CONFIRMADA" and reserva["fim"] <= datetime.now(timezone.utc):
            situacao = "Confirmada (período encerrado)"

        recurso = (
            f'{reserva["tipo_recurso"]} — '
            f'{reserva["recurso_nome"]}'
        )

        titular = (
            escape(reserva["usuario_nome"])
            if eh_chefe
            else "Você"
        )

        pode_cancelar = (
            estado == "CONFIRMADA"
            and reserva["fim"] > datetime.now(timezone.utc)
            and (
                ator.id == reserva["usuario_id"]
                or eh_chefe
            )
        )

        acao = "—"

        if pode_cancelar:
            acao = (
                '<form method="post" '
                'action="/reservas/cancelar">'
                + oculto(csrf)
                + '<input type="hidden" '
                'name="reserva_id" '
                f'value="{int(reserva["id"])}">'
                '<label>Motivo'
                '<input type="text" name="motivo" '
                'maxlength="300" required '
                'placeholder="Informe o motivo">'
                '</label>'
                '<button type="submit" '
                'class="secundario">'
                'Cancelar reserva'
                '</button>'
                '</form>'
            )

        detalhe = ""

        if (
            estado == "CANCELADA"
            and reserva["motivo_cancelamento"]
        ):
            detalhe = (
                '<p>Motivo: '
                + escape(
                    str(reserva["motivo_cancelamento"])
                )
                + '</p>'
            )

        local = reserva.get("local_registrado") or {}
        descricao_local = ' / '.join(str(local[k]) for k in ("sala_localizacao", "sala_identificacao", "bancada_identificacao", "complemento_local") if local.get(k))
        linhas.append(
            '<tr>'
            f'<td>#{int(reserva["id"])}</td>'
            f'<td>{escape(recurso)}<p>{escape(descricao_local)}</p></td>'
            f'<td>{escape(periodo)}</td>'
            f'<td>{titular}</td>'
            f'<td>{escape(situacao)}{detalhe}</td>'
            f'<td>{acao}</td>'
            '</tr>'
        )

    corpo += (
        '<section class="cartao">'
        '<p>Exibindo até 100 reservas recentes. '
        'Horários de Brasília.</p>'
        '<table>'
        '<thead><tr>'
        '<th>ID</th>'
        '<th>Recurso</th>'
        '<th>Período</th>'
        '<th>Titular</th>'
        '<th>Estado</th>'
        '<th>Ação</th>'
        '</tr></thead>'
        '<tbody>'
        + "".join(linhas)
        + '</tbody></table>'
        '</section>'
    )

    return layout(
        titulo,
        corpo,
        ator,
        csrf
    )




def pagina_historico(
    ator,
    csrf,
    eventos,
    recursos,
    usuarios,
    filtros=None,
    mensagem=""
):
    from datetime import timedelta, timezone

    filtros = filtros or {}

    eh_chefe = isinstance(ator, ChefeLaboratorio)

    # Opções para filtrar por recurso.
    opcoes_recursos = [
        (
            recurso.id,
            f"{type(recurso).__name__} — {recurso.nome} — {getattr(recurso, 'numero_patrimonio', getattr(recurso, 'identificacao', getattr(recurso, 'numero_identificacao', '')))}"
        )
        for recurso in recursos
        if recurso.id is not None
    ]

    campos = _selecao_recurso(
        "recurso_id",
        "Recurso",
        opcoes_recursos,
        filtros.get("recurso_id", ""),
        obrigatorio=False
    )

    # Somente o Chefe pode pesquisar por outro usuário.
    if eh_chefe:
        opcoes_usuarios = [
            (usuario.id, usuario.nome)
            for usuario in usuarios
            if usuario.id is not None
        ]

        campos += _selecao_recurso(
            "usuario_id",
            "Usuário",
            opcoes_usuarios,
            filtros.get("usuario_id", ""),
            obrigatorio=False
        )

    campos += (
        campo(
            "desde",
            "Eventos a partir de",
            filtros.get("desde", ""),
            tipo="date",
            obrigatorio=False
        )
        + campo(
            "ate",
            "Eventos até",
            filtros.get("ate", ""),
            tipo="date",
            obrigatorio=False
        )
    )

    corpo = aviso(mensagem, True)

    corpo += (
        '<section class="cartao">'
        '<h2>Consultar histórico</h2>'
        '<p>Os filtros por data consideram quando '
        'o evento foi registrado, e não a data '
        'agendada da reserva.</p>'
        '<form method="get" action="/historico">'
        f'<div class="campos">{campos}</div>'
        '<div class="acoes">'
        '<button type="submit">Filtrar</button>'
        '<a href="/historico">Limpar filtros</a>'
        '</div></form></section>'
    )

    if not eventos:
        corpo += (
            '<section class="cartao">'
            '<p>Nenhum evento encontrado.</p>'
            '</section>'
        )
        return layout(
            "Histórico de operações",
            corpo,
            ator,
            csrf
        )

    fuso = timezone(timedelta(hours=-3))
    linhas = []

    for evento in eventos:

        if evento.descricao:
            descricao = evento.descricao
        elif evento.eh_cancelamento():
            descricao = (
                f"Reserva #{evento.registro_id} cancelada"
            )

        elif (
            evento.tabela == "reserva"
            and evento.acao == "INSERT"
        ):
            descricao = (
                f"Reserva #{evento.registro_id} criada"
            )

        elif evento.tabela == "reserva_recurso":
            dados = evento.depois or evento.antes or {}

            reserva_id = dados.get("reserva_id", "?")
            recurso_id = dados.get("recurso_id", "?")

            if evento.acao == "INSERT":
                descricao = (
                    f"Recurso #{recurso_id} incluído "
                    f"na reserva #{reserva_id}"
                )
            else:
                descricao = (
                    f"Recurso #{recurso_id} atualizado "
                    f"na reserva #{reserva_id}"
                )

        else:
            descricao = (
                f"Registro {evento.registro_id} atualizado"
            )

        data_local = evento.registrado_em.astimezone(
            fuso
        )

        data_formatada = data_local.strftime(
            "%d/%m/%Y %H:%M"
        )

        responsavel = (
            evento.ator_nome or str(evento.ator_id)
            if evento.ator_id is not None
            else "Sistema"
        )

        motivo = evento.motivo or "—"

        linhas.append(
            "<tr>"
            f"<td>#{evento.id}</td>"
            f"<td>{escape(data_formatada)}</td>"
            f"<td>{escape(descricao)}<p>{escape(evento.recurso_nome or '')} — {escape(evento.usuario_nome or '')}</p></td>"
            f"<td>{escape(responsavel)}</td>"
            f"<td>{escape(str(motivo))}</td>"
            "</tr>"
        )

    corpo += (
        '<section class="cartao">'
        '<h2>Eventos registrados</h2>'
        '<p>Exibindo até 100 eventos mais recentes. '
        'Horários de Brasília.</p>'
        '<div class="tabela">'
        '<table>'
        '<thead><tr>'
        '<th>ID</th>'
        '<th>Data e hora</th>'
        '<th>Evento</th>'
        '<th>Responsável</th>'
        '<th>Motivo</th>'
        '</tr></thead>'
        f'<tbody>{"".join(linhas)}</tbody>'
        '</table></div></section>'
    )

    return layout(
        "Histórico de operações",
        corpo,
        ator,
        csrf
    )



def formulario_limites_reserva(
    ator,
    csrf,
    laboratorio,
    dados=None,
    mensagem="",
    sucesso=""
):
    # Exibe os valores atuais quando o formulário
    # ainda não foi enviado.
    if dados is None:
        duracao = (
            str(int(
                laboratorio.duracao_maxima_reserva.total_seconds()
                / 60
            ))
            if laboratorio.duracao_maxima_reserva is not None
            else ""
        )

        quantidade = (
            str(laboratorio.max_reservas_simultaneas)
            if laboratorio.max_reservas_simultaneas is not None
            else ""
        )

    else:
        # Preserva os campos preenchidos se houver erro.
        duracao = str(
            dados.get("duracao_minutos", "")
        )

        quantidade = str(
            dados.get("quantidade", "")
        )

    # Formulário HTML.
    campos = (
        '<label>Duração máxima por reserva (minutos)'
        '<input type="number" '
        'name="duracao_minutos" '
        'min="1" step="1" '
        f'value="{escape(duracao, quote=True)}">'
        '</label>'

        '<label>Quantidade máxima de reservas '
        'simultâneas por usuário'
        '<input type="number" '
        'name="quantidade" '
        'min="1" step="1" '
        f'value="{escape(quantidade, quote=True)}">'
        '</label>'
    )

    corpo = aviso(sucesso) + aviso(mensagem, True)

    corpo += (
        '<section class="cartao">'
        '<p>Configure os limites válidos para novas '
        'reservas do laboratório.</p>'

        '<p>Deixe um campo vazio para não '
        'estabelecer esse limite.</p>'

        '<form method="post" action="/limites-reserva">'
        + oculto(csrf)
        + f'<div class="campos">{campos}</div>'
        + '<div class="acoes">'
        '<button type="submit">Salvar limites</button>'
        '<a href="/reservas">Voltar às reservas</a>'
        '</div></form></section>'
    )

    return layout(
        "Limites de reserva",
        corpo,
        ator,
        csrf
    )



def formulario_vinculos_equipamento(
    ator, csrf, bancadas, equipamentos,
    dados=None, mensagem="", sucesso=""
):
    dados = dados or {}

    # Equipamentos disponíveis para seleção.
    opcoes_equipamentos = [
        (e.id, f"{e.numero_patrimonio} — {e.nome}")
        for e in equipamentos
        if e.id is not None
    ]

    # Bancadas do laboratório.
    opcoes_bancadas = [
        (b.id, f"{b.numero_identificacao} — {b.nome}")
        for b in bancadas
        if b.id is not None
    ]

    # Equipamentos atualmente vinculados a bancadas.
    vinculados = [
        e for e in equipamentos
        if e.id is not None and e.bancada_id is not None
    ]

    opcoes_vinculados = [
        (
            e.id,
            f"{e.numero_patrimonio} — {e.nome} "
            f"(bancada #{e.bancada_id})"
        )
        for e in vinculados
    ]

    corpo = aviso(sucesso) + aviso(mensagem, True)

    # FORMULÁRIO 1: Vincular ou trocar de bancada.
    corpo += (
        '<section class="cartao">'
        '<p>Somente o Chefe pode alterar vínculos. '
        'Alterações que afetem reservas confirmadas '
        'poderão ser bloqueadas.</p>'
        '<h2>Vincular ou trocar de bancada</h2>'
    )

    if equipamentos and bancadas:
        campos = (
            _selecao_recurso(
                "equipamento_id",
                "Equipamento",
                opcoes_equipamentos,
                dados.get("equipamento_id", "")
            )
            + _selecao_recurso(
                "bancada_id",
                "Bancada de destino",
                opcoes_bancadas,
                dados.get("bancada_id", "")
            )
            + campo(
                "complemento_local",
                "Complemento do local (opcional)",
                dados.get("complemento_local", ""),
                obrigatorio=False,
                limite=200
            )
        )

        corpo += (
            '<form method="post" '
            'action="/recursos/vinculos">'
            + oculto(csrf)
            + '<input type="hidden" '
            'name="acao" value="vincular">'
            + f'<div class="campos">{campos}</div>'
            + '<div class="acoes">'
            '<button type="submit">Salvar vínculo</button>'
            '</div></form>'
        )
    else:
        corpo += (
            '<p>Cadastre um equipamento e uma '
            'bancada primeiro.</p>'
        )

    corpo += '</section>'

    # FORMULÁRIO 2: Desvincular da bancada.
    corpo += (
        '<section class="cartao">'
        '<h2>Desvincular da bancada</h2>'
    )

    if vinculados:
        campos = _selecao_recurso(
            "equipamento_id",
            "Equipamento vinculado",
            opcoes_vinculados,
            (
                dados.get("equipamento_id", "")
                if dados.get("acao") == "desvincular"
                else ""
            )
        )

        campos += campo("complemento_local", "Posição na sala (opcional)", dados.get("complemento_local", ""), obrigatorio=False, limite=200)

        corpo += (
            '<p>O equipamento continuará na sala '
            'da bancada atual.</p>'
            '<form method="post" '
            'action="/recursos/vinculos">'
            + oculto(csrf)
            + '<input type="hidden" '
            'name="acao" value="desvincular">'
            + f'<div class="campos">{campos}</div>'
            + '<div class="acoes">'
            '<button type="submit" class="secundario">'
            'Desvincular equipamento'
            '</button></div></form>'
        )
    else:
        corpo += (
            '<p>Não há equipamentos vinculados '
            'a bancadas.</p>'
        )

    corpo += '</section>'

    # LISTAGEM: Localização atual dos equipamentos.
    descricoes = []

    for e in equipamentos:
        local = (
            f"Bancada #{e.bancada_id}"
            if e.bancada_id is not None
            else f"Sala #{e.sala_direta_id} (sem bancada)"
        )

        descricoes.append(
            f'<li>{escape(e.numero_patrimonio)} — '
            f'{escape(e.nome)}: {escape(local)}</li>'
        )

    corpo += (
        '<section class="cartao">'
        '<h2>Localização atual</h2>'
        + (
            '<ul>' + ''.join(descricoes) + '</ul>'
            if descricoes
            else '<p>Não há equipamentos cadastrados.</p>'
        )
        + '<a href="/recursos">'
        'Voltar aos recursos</a>'
        '</section>'
    )

    return layout(
        "Vínculos de equipamentos",
        corpo,
        ator,
        csrf
    )


def _selecao_responsavel(ator, dados, responsaveis):
    return _selecao_recurso("responsavel_id", "Professor responsável", [(u.id, u.nome) for u in (responsaveis or [ator])], dados.get("responsavel_id", ator.id))


def formulario_localizacao(ator, csrf, equipamento, salas, bancadas, dados=None, mensagem=""):
    dados = dados if dados is not None else {"bancada_id": equipamento.bancada_id or "",
        "sala_direta_id": equipamento.sala_direta_id or "", "complemento_local": equipamento.complemento_local}
    campos = f'<input type="hidden" name="equipamento_id" value="{equipamento.id}">'
    salas_por_id = {s.id: s for s in salas}
    campos += _selecao_recurso("bancada_id", "Bancada (opcional)", [(b.id, f'{salas_por_id[b.sala_id].identificacao} / {b.numero_identificacao} — {b.nome}') for b in bancadas], dados.get("bancada_id", ""), False)
    campos += _selecao_recurso("sala_direta_id", "Sala direta (opcional)", [(s.id, f'{s.identificacao} — {s.nome}') for s in salas], dados.get("sala_direta_id", ""), False)
    campos += campo("complemento_local", "Complemento do local", dados.get("complemento_local", ""), limite=200)
    corpo = aviso(mensagem, True) + f'''<section class="cartao estreito"><p>{escape(equipamento.numero_patrimonio)} — {escape(equipamento.nome)}</p>
<p>Selecione uma bancada ou uma sala direta. Reservas ativas ou futuras que envolvam a alteração devem ser regularizadas antes da mudança.</p>
<form method="post" action="/recursos/localizacao">{oculto(csrf)}{campos}<div class="acoes"><button>Salvar localização</button><a href="/recursos">Voltar</a></div></form></section>'''
    return layout("Alterar localização", corpo, ator, csrf)
