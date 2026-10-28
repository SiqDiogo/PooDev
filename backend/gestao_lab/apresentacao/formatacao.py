def horario(instante, fuso):
    return instante.astimezone(fuso).strftime("%d/%m/%Y %H:%M")


def nome_fuso(fuso):
    return "horário de Brasília"
