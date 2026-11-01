
## Regras de trabalho

- Busque sempre ser o mais simples e direto possível!

- Especificaçõesm em SPECS.md

1. Não faça commits NUNCA
5. Não presuma arquitetura, dependências ou fluxos de negócio: confirme tudo no código.
6. Não altere arquivos antes de apresentar o diagnóstico e o plano de trabalho.
7. Trabalhe incrementalmente e revise os diffs após cada etapa.
8. Não execute commits, pushes ou operações destrutivas sem autorização explícita.
9. Preserve alterações locais preexistentes.
10. Consulte os arquivos `AGENTS.md` específicos do backend e frontend, caso existam, antes de modificar esses projetos.
11. Trabalhe sempre na branch atualmente ativa, consulte outras branches somente quando necessário ou solicitado.
12. Nos testes prefira o uso de testcontainer com MSSQL, evite os mocks do jest ao lidar com banco e TypeORM



Bibliotecas:

- beautifulsoup4
- requests
- curl-cffi (para fingerprint amazon)