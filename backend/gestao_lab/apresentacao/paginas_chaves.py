from html import escape

from .paginas import aviso, campo, layout, oculto, _selecao_recurso
from .formatacao import horario, nome_fuso
from ..dominio.usuarios import ChefeLaboratorio

ESTADOS = {"DISPONIVEL": "Disponível", "EM_USO": "Em uso", "EXTRAVIADA": "Extraviada", "INDISPONIVEL": "Indisponível"}


def painel(ator, csrf, copias, destinos, emprestimos, fuso, mensagem=""):
    corpo = aviso(mensagem)
    if destinos:
        corpo += '<p><a class="botao" href="/chaves/nova">Cadastrar cópia de chave</a></p>'
    corpo += '<p>A reserva autoriza a retirada de uma cópia compatível. A entrega e o recebimento físicos são registrados pelo Chefe ou Professor responsável pelo local.</p>'
    linhas = []
    for c in copias:
        gestor = c.destino.pode_gerenciar(ator)
        acoes = ''
        if gestor:
            acoes = f'<a href="/chaves/designar?id={c.id}">Designar</a> · <a href="/chaves/ocorrencia?id={c.id}">Registrar ocorrência</a>'
            if c.estado == "DISPONIVEL":
                acoes += f' · <a href="/chaves/retirar?id={c.id}">Registrar retirada</a>'
        portador = c.portador_nome if gestor or c.portador_id == ator.id else None
        linhas.append(f'<tr><td>{escape(c.codigo_copia)}</td><td>{escape(c.destino.nome)} — {escape(c.destino.local)}</td>'
            f'<td>{escape(c.designada_nome or "Compartilhada")}</td><td>{ESTADOS[c.estado]}</td>'
            f'<td>{escape(portador or "—")}</td><td>{acoes or "—"}</td></tr>')
    corpo += f'''<section class="cartao"><h2>Cópias de chaves</h2><div class="tabela"><table>
<thead><tr><th>Código</th><th>Local de acesso</th><th>Designação</th><th>Estado</th><th>Em posse de</th><th>Ações</th></tr></thead>
<tbody>{''.join(linhas) or '<tr><td colspan="6">Nenhuma cópia disponível para consulta.</td></tr>'}</tbody></table></div></section>'''
    linhas = []
    for e in emprestimos:
        acao = f'<a href="/chaves/devolver?id={e.id}">Registrar devolução</a>' if e.devolucao_em is None and e.destino.pode_gerenciar(ator) else '—'
        linhas.append(f'<tr><td>{escape(e.codigo_copia)} — {escape(e.destino.nome)}</td><td>{escape(e.usuario_nome)}</td>'
            f'<td>#{e.reserva_id}</td><td>{horario(e.retirada_em, fuso)}<br>{escape(e.entregue_nome)}</td>'
            f'<td>{horario(e.devolucao_em, fuso) if e.devolucao_em else "Em aberto"}<br>{escape(e.recebido_nome or "")}</td><td>{acao}</td></tr>')
    corpo += f'''<section class="cartao"><h2>Retiradas e devoluções</h2>
<p>Você vê seus empréstimos e os dos locais que pode gerenciar. Datas e horas no {nome_fuso(fuso)}.</p>
<div class="tabela"><table><thead><tr><th>Cópia</th><th>Portador</th><th>Reserva</th><th>Entrega</th><th>Recebimento</th><th>Ação</th></tr></thead>
<tbody>{''.join(linhas) or '<tr><td colspan="6">Nenhum empréstimo registrado.</td></tr>'}</tbody></table></div></section>
<p><a href="/historico">Consultar histórico de operações</a></p>'''
    return layout("Chaves", corpo, ator, csrf)


def formulario(rota, titulo, campos, ator, csrf, mensagem="", instrucao=""):
    return layout(titulo, aviso(mensagem, True) + f'''<section class="cartao estreito"><p>{escape(instrucao)}</p>
<form method="post" action="{rota}">{oculto(csrf)}{campos}
<div class="acoes"><button>Salvar</button><a href="/chaves">Voltar</a></div></form></section>''', ator, csrf)


def selecao_designacao(usuarios, valor=""):
    return _selecao_recurso("designada_para", "Designar a (em branco: compartilhada)",
                           [(u.id, u.nome) for u in usuarios], valor, False)


def nova(ator, csrf, destinos, usuarios, dados=None, mensagem=""):
    dados = dados or {}
    campos = campo("codigo_copia", "Código único da cópia", dados.get("codigo_copia", ""), limite=80)
    campos += _selecao_recurso("destino_id", "Sala ou bancada de acesso", [(d.id, f'{d.nome} — {d.local}') for d in destinos], dados.get("destino_id", ""))
    campos += selecao_designacao(usuarios, dados.get("designada_para", ""))
    return formulario("/chaves/nova", "Cadastrar cópia de chave", campos, ator, csrf, mensagem,
                       "Cadastre cada cópia física separadamente. A cópia começa disponível e operacional.")


def designar(ator, csrf, copia, usuarios, dados=None, mensagem=""):
    dados = dados if dados is not None else {"designada_para": copia.designada_para or ""}
    campos = f'<p>{escape(copia.codigo_copia)} — {escape(copia.destino.nome)}</p><input type="hidden" name="chave_id" value="{copia.id}">'
    campos += selecao_designacao(usuarios, dados.get("designada_para", ""))
    return formulario("/chaves/designar", "Designar cópia", campos, ator, csrf, mensagem,
                       "A designação restringe o portador autorizado. Uma cópia emprestada precisa ser devolvida antes da alteração.")


def retirar(ator, csrf, copia, reservas, fuso, dados=None, mensagem=""):
    dados = dados or {}
    campos = f'<p>{escape(copia.codigo_copia)} — {escape(copia.destino.nome)}</p><input type="hidden" name="chave_id" value="{copia.id}">'
    campos += _selecao_recurso("reserva_id", "Reserva autorizada", [
        (r.id, f'#{r.id} — {r.usuario_nome} — {r.recurso_nome} — {horario(r.inicio, fuso)} até {horario(r.fim, fuso)}') for r in reservas], dados.get("reserva_id", ""))
    if not reservas:
        campos += '<p>Nenhuma reserva confirmada autoriza esta cópia para um usuário ativo.</p>'
    corpo = aviso(mensagem, True) + f'''<section class="cartao estreito"><p>Confirme somente ao entregar a cópia física ao dono da reserva. A reserva será validada novamente na confirmação.</p>
<form method="post" action="/chaves/retirar">{oculto(csrf)}{campos}<div class="acoes">
{'<button>Confirmar entrega física</button>' if reservas else ''}<a href="/chaves">Voltar</a></div></form></section>'''
    return layout("Registrar retirada de chave", corpo, ator, csrf)


def devolver(ator, csrf, emprestimo, mensagem=""):
    corpo = aviso(mensagem, True) + f'''<section class="cartao estreito">
<p>Confirmar o recebimento físico de <strong>{escape(emprestimo.codigo_copia)}</strong>, em posse de {escape(emprestimo.usuario_nome)}?</p>
<p>Uma ocorrência de extravio ou indisponibilidade permanece registrada após a devolução. Registre a condição operacional quando a cópia for conferida.</p>
<form method="post" action="/chaves/devolver">{oculto(csrf)}<input type="hidden" name="emprestimo_id" value="{emprestimo.id}">
<div class="acoes"><button>Confirmar recebimento físico</button><a href="/chaves">Voltar</a></div></form></section>'''
    return layout("Registrar devolução de chave", corpo, ator, csrf)


def ocorrencia(ator, csrf, copia, dados=None, mensagem=""):
    dados = dados or {}
    campos = f'<p>{escape(copia.codigo_copia)} — {escape(copia.destino.nome)}</p><input type="hidden" name="chave_id" value="{copia.id}">'
    campos += _selecao_recurso("condicao", "Condição da cópia", [("EXTRAVIADA", "Extraviada"), ("INDISPONIVEL", "Indisponível"), ("OPERACIONAL", "Operacional após conferência")], dados.get("condicao", ""))
    campos += f'<label>Descrição<textarea name="descricao" required maxlength="500">{escape(dados.get("descricao", ""))}</textarea></label>'
    return formulario("/chaves/ocorrencia", "Registrar ocorrência de chave", campos, ator, csrf, mensagem,
                       "A ocorrência altera a condição da cópia e preserva a posse de um empréstimo ainda aberto.")

