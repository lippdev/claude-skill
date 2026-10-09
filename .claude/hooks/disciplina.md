<!--
Disciplina de resposta do Token Pilot. O hook token_pilot.py injeta a seção "edição" na sessão
principal e nos agentes que editam, e a seção "leitura" nos agentes somente leitura.
Cada linha entra no contexto de toda sessão: mantenha curto.
Inspirado no ponytail (github.com/dietrichgebert/ponytail, licença MIT).
-->

## edição

[Token Pilot] Disciplina de resposta: a menor mudança que resolve a tarefa inteira.
- Antes de editar, leia o código que a mudança toca e liste tudo que ela precisa alcançar: chamadas, testes, fixtures, config, exports. Em correção de bug, ache com grep todos os usos da função antes de mexer e corrija a causa uma vez, no código compartilhado.
- Escolha a primeira opção que funciona: (1) precisa existir? (2) já existe no projeto? use do mesmo jeito; (3) biblioteca padrão; (4) dependência já instalada; (5) uma linha legível; (6) só então código novo, o mínimo.
- Sem abstração, opção, configuração ou código "para depois" que ninguém pediu. Apagar vale mais que adicionar. Mantenha a estrutura e as convenções do projeto.
- Lógica nova com ramo, laço, parser, dinheiro ou segurança ganha um teste pequeno. Mudança trivial não precisa.
- Atalho com limite conhecido ganha o comentário `atalho: <limite>, <quando melhorar>`.
- Nunca corte: validação de entrada externa, tratamento de erro que evita perda de dados, segurança, acessibilidade, nem nada que o usuário pediu.
- Resposta curta: o que mudou, como foi verificado, e uma linha com o que ficou de fora ou o risco.

## leitura

[Token Pilot] Disciplina de resposta: leia só o necessário e devolva só a conclusão.
- Use grep, glob, head e tail antes de abrir arquivos inteiros.
- Responda no formato pedido, com `caminho:linha`, sem colar arquivos nem repetir a pergunta.
- Diga o que não conseguiu confirmar em uma linha.
