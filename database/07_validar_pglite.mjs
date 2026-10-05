// Validação reproduzível, sem conexão externa, em PostgreSQL via WebAssembly.
// npm install; npm test. Não substitui o teste de duas conexões do arquivo 06.
import {PGlite} from '@electric-sql/pglite';
import {btree_gist} from '@electric-sql/pglite/contrib/btree_gist';
import {readFile} from 'node:fs/promises';

const db=await PGlite.create({extensions:{btree_gist}});
try {
  const version=(await db.query('SELECT version()')).rows[0].version;
  console.log(version);
  for(const file of ['BancoLaboratorioPostgreSQL.sql','03_dados_exemplo.sql','04_consultas_exemplo.sql','05_testes_integridade.sql']) {
    const result=await db.exec(await readFile(new URL(file,import.meta.url),'utf8'));
    console.log(file+': OK');
    for(const statement of result) {
      if(statement.rows?.some(row=>'testes_aprovados' in row)) console.log(statement.rows);
    }
  }
} catch(error) {
  console.error(JSON.stringify({erro:error.message,sqlstate:error.code,contexto:error.where},null,2));
  process.exitCode=1;
} finally {
  await db.close();
}
