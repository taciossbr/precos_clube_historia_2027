# Ideia: paralelizar coletas por plataforma

## Objetivo

Diminuir o tempo total da execução no GitHub Actions executando Amazon, Mercado Livre e Estante Virtual ao mesmo tempo, sem fazer requisições simultâneas para uma mesma plataforma.

## O que o código faz hoje

`main.py` percorre cada livro e, dentro dele, cada link em sequência. O intervalo com jitter de 12 segundos é aplicado entre todas as chamadas, mesmo quando as chamadas são de plataformas diferentes. A Amazon ainda tem seus próprios atrasos entre retries.

## Proposta

- Separar os links da execução em três filas: Amazon, Mercado Livre e Estante Virtual.
- Executar no máximo um worker por plataforma.
- Cada worker percorre sua fila em sequência; assim, não há duas requisições simultâneas para a mesma plataforma.
- Manter os retries e as pausas da Amazon dentro da fila Amazon.
- Aplicar o intervalo entre chamadas consecutivas dentro de cada fila, em vez de usar um único intervalo global entre plataformas.
- Ao terminar as filas, juntar os resultados na ordem original de `produto.links`, processar métricas e persistir os arquivos como hoje.
- Em `--plataforma`, executar somente a fila solicitada e continuar reutilizando os resultados anteriores das outras plataformas.

## Cuidados de implementação

- Não chamar `registrar_resultado` pelos workers. Essa função lê e substitui `erros_consecutivos.json`; chamadas simultâneas poderiam sobrescrever atualizações umas das outras. Os workers devem retornar os resultados e o fluxo principal registra os contadores em sequência depois da coleta.
- Cada coletor deve continuar limitado à sua própria fila. Não paralelizar links da Amazon entre si, nem links do Mercado Livre ou da Estante Virtual entre si.
- Preservar a ordem de resultados esperada por `processar_produto` e os contadores por URL.
- Só persistir histórico, consolidado e alertas depois que todos os resultados estiverem reunidos.
- As chamadas das três plataformas aconteceriam simultaneamente; o limite proposto é por plataforma, não um limite global de uma única requisição por vez.

## Viabilidade e ganho esperado

É viável no GitHub Actions com threads, pois as coletas passam a maior parte do tempo aguardando rede, espera do navegador ou intervalos. O tempo total tende a se aproximar do tempo da fila mais lenta, em vez da soma do tempo das três plataformas. A economia exata depende de retries, latência e quantidade de links em cada fila.

Essa mudança não reduz as requisições enviadas a nenhuma plataforma. Ela mantém cada plataforma sequencial e sobrepõe o tempo de espera de uma plataforma ao trabalho das outras.

## Validação antes de ativar

- Confirmar que os contadores por URL não perdem atualizações.
- Confirmar que o resultado consolidado mantém os links na ordem original.
- Confirmar que uma falha em uma plataforma não impede as outras filas de concluírem.
- Comparar a duração total e a cadência das requisições por plataforma em uma execução do Actions.

**Status:** proposta registrada; paralelismo ainda não implementado.
