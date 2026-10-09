from html import escape

from ..dominio.usuarios import Aluno, ChefeLaboratorio, Perfil, Professor, TipoAluno

ROTULOS = {Perfil.ALUNO: "Aluno", Perfil.PROFESSOR: "Professor", Perfil.CHEFE: "Chefe de Laboratório"}
CATEGORIAS = {TipoAluno.GRADUACAO: "Graduação", TipoAluno.MESTRADO: "Mestrado",
              TipoAluno.DOUTORADO: "Doutorado", TipoAluno.POS: "Pós"}


def oculto(csrf):
    return f'<input type="hidden" name="csrf" value="{escape(csrf, quote=True)}">'


def layout(titulo, conteudo, usuario=None, csrf=""):
    nav = ''
    if usuario:
        links = '<a href="/">Meu perfil</a>'
        if isinstance(usuario, ChefeLaboratorio):
            links += '<a href="/usuarios">Usuários</a><a href="/cadastros/aluno">Cadastrar aluno</a><a href="/cadastros/professor">Cadastrar professor</a>'
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
        detalhe = f'Matrícula: {u.matricula}' if isinstance(u, Aluno) else u.programa_pos
        linhas.append(f'<tr><td>{escape(u.nome)}</td><td>{escape(u.email)}</td><td>{ROTULOS[u.perfil]}</td><td>{escape(detalhe)}</td><td>{"Ativo" if u.ativo else "Inativo"}</td></tr>')
    corpo = aviso(mensagem) + f'''<p>Contas vinculadas ao seu laboratório.</p>
<div class="acoes"><a class="botao" href="/cadastros/aluno">Cadastrar aluno</a><a class="botao secundario" href="/cadastros/professor">Cadastrar professor</a></div>
<div class="tabela"><table><thead><tr><th>Nome</th><th>E-mail</th><th>Perfil</th><th>Dados acadêmicos</th><th>Situação</th></tr></thead><tbody>{''.join(linhas)}</tbody></table></div>'''
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
