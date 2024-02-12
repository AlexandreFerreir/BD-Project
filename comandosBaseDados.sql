--------------------------------------BD SCRIPT--------------------------------


CREATE TABLE consumidor (
	nome			 VARCHAR(512),
	endereco		 VARCHAR(512),
	data_de_nascimento	 DATE,
	informacoes_de_contacto VARCHAR(512),
	utilizador_id		 INTEGER,
	PRIMARY KEY(utilizador_id)
);

CREATE TABLE subscricao (
	id			 INTEGER,
	tipo_de_plano		 VARCHAR(512),
	data_de_inicio		 DATE,
	data_de_validade	 DATE,
	consumidor_utilizador_id INTEGER NOT NULL,
	PRIMARY KEY(id)
);

CREATE TABLE cartao_pre_pago (
	id				 BIGINT,
	valor			 FLOAT(8),
	data_de_validade		 DATE,
	valor_restante		 FLOAT(8),
	administrador_utilizador_id INTEGER NOT NULL,
	PRIMARY KEY(id)
);

CREATE TABLE musica (
	ismn		 INTEGER,
	titulo		 VARCHAR(512),
	genero		 VARCHAR(512),
	duracao		 FLOAT(8),
	data_de_lancamento DATE,
	gravadora_id	 INTEGER NOT NULL,
	PRIMARY KEY(ismn)
);

CREATE TABLE album (
	id		 INTEGER,
	titulo		 VARCHAR(512),
	data_de_lancamento DATE,
	gravadora_id	 INTEGER NOT NULL,
	PRIMARY KEY(id)
);

CREATE TABLE playlist (
	id			 INTEGER,
	nome			 VARCHAR(512),
	visibilidade		 BOOL,
	consumidor_utilizador_id INTEGER NOT NULL,
	PRIMARY KEY(id)
);

CREATE TABLE comentario (
	id			 INTEGER,
	texto			 VARCHAR(512),
	data_de_criacao		 DATE,
	musica_ismn		 INTEGER NOT NULL,
	consumidor_utilizador_id INTEGER NOT NULL,
	PRIMARY KEY(id)
);

CREATE TABLE gravadora (
	id			 INTEGER,
	nome			 VARCHAR(512),
	informacao_de_contacto VARCHAR(512),
	PRIMARY KEY(id)
);

CREATE TABLE artista (
	nome			 VARCHAR(512),
	nome_artistico		 VARCHAR(512),
	endereco			 VARCHAR(512),
	data_de_nascimento		 DATE,
	informacoes_de_contacto	 VARCHAR(512),
	administrador_utilizador_id INTEGER NOT NULL,
	utilizador_id		 INTEGER,
	PRIMARY KEY(utilizador_id)
);

CREATE TABLE administrador (
	utilizador_id INTEGER,
	PRIMARY KEY(utilizador_id)
);

CREATE TABLE utilizador (
	id		 INTEGER,
	username	 VARCHAR(512),
	palavra_passe VARCHAR(512),
	PRIMARY KEY(id)
);

CREATE TABLE contagem_musica (
	data			 DATE,
	id			 INTEGER,
	consumidor_utilizador_id INTEGER NOT NULL,
	musica_ismn		 INTEGER NOT NULL,
	PRIMARY KEY(id)
);

CREATE TABLE comentario_comentario (
	comentario_id	 INTEGER,
	comentario_id1 INTEGER,
	PRIMARY KEY(comentario_id,comentario_id1)
);

CREATE TABLE musica_playlist (
	musica_ismn INTEGER,
	playlist_id INTEGER,
	PRIMARY KEY(musica_ismn,playlist_id)
);

CREATE TABLE subscricao_cartao_pre_pago (
	subscricao_id	 INTEGER,
	cartao_pre_pago_id BIGINT,
	PRIMARY KEY(subscricao_id,cartao_pre_pago_id)
);

CREATE TABLE album_artista (
	album_id		 INTEGER,
	artista_utilizador_id INTEGER,
	PRIMARY KEY(album_id,artista_utilizador_id)
);

CREATE TABLE artista_musica (
	artista_utilizador_id INTEGER,
	musica_ismn		 INTEGER,
	PRIMARY KEY(artista_utilizador_id,musica_ismn)
);

CREATE TABLE musica_album (
	musica_ismn INTEGER,
	album_id	 INTEGER,
	PRIMARY KEY(musica_ismn,album_id)
);

ALTER TABLE consumidor ADD CONSTRAINT consumidor_fk1 FOREIGN KEY (utilizador_id) REFERENCES utilizador(id);
ALTER TABLE subscricao ADD CONSTRAINT subscricao_fk1 FOREIGN KEY (consumidor_utilizador_id) REFERENCES consumidor(utilizador_id);
ALTER TABLE cartao_pre_pago ADD CONSTRAINT cartao_pre_pago_fk1 FOREIGN KEY (administrador_utilizador_id) REFERENCES administrador(utilizador_id);
ALTER TABLE musica ADD CONSTRAINT musica_fk1 FOREIGN KEY (gravadora_id) REFERENCES gravadora(id);
ALTER TABLE album ADD CONSTRAINT album_fk1 FOREIGN KEY (gravadora_id) REFERENCES gravadora(id);
ALTER TABLE playlist ADD CONSTRAINT playlist_fk1 FOREIGN KEY (consumidor_utilizador_id) REFERENCES consumidor(utilizador_id);
ALTER TABLE comentario ADD CONSTRAINT comentario_fk1 FOREIGN KEY (musica_ismn) REFERENCES musica(ismn);
ALTER TABLE comentario ADD CONSTRAINT comentario_fk2 FOREIGN KEY (consumidor_utilizador_id) REFERENCES consumidor(utilizador_id);
ALTER TABLE artista ADD CONSTRAINT artista_fk1 FOREIGN KEY (administrador_utilizador_id) REFERENCES administrador(utilizador_id);
ALTER TABLE artista ADD CONSTRAINT artista_fk2 FOREIGN KEY (utilizador_id) REFERENCES utilizador(id);
ALTER TABLE administrador ADD CONSTRAINT administrador_fk1 FOREIGN KEY (utilizador_id) REFERENCES utilizador(id);
ALTER TABLE contagem_musica ADD CONSTRAINT contagem_musica_fk1 FOREIGN KEY (consumidor_utilizador_id) REFERENCES consumidor(utilizador_id);
ALTER TABLE contagem_musica ADD CONSTRAINT contagem_musica_fk2 FOREIGN KEY (musica_ismn) REFERENCES musica(ismn);
ALTER TABLE comentario_comentario ADD CONSTRAINT comentario_comentario_fk1 FOREIGN KEY (comentario_id) REFERENCES comentario(id);
ALTER TABLE comentario_comentario ADD CONSTRAINT comentario_comentario_fk2 FOREIGN KEY (comentario_id1) REFERENCES comentario(id);
ALTER TABLE musica_playlist ADD CONSTRAINT musica_playlist_fk1 FOREIGN KEY (musica_ismn) REFERENCES musica(ismn);
ALTER TABLE musica_playlist ADD CONSTRAINT musica_playlist_fk2 FOREIGN KEY (playlist_id) REFERENCES playlist(id);
ALTER TABLE subscricao_cartao_pre_pago ADD CONSTRAINT subscricao_cartao_pre_pago_fk1 FOREIGN KEY (subscricao_id) REFERENCES subscricao(id);
ALTER TABLE subscricao_cartao_pre_pago ADD CONSTRAINT subscricao_cartao_pre_pago_fk2 FOREIGN KEY (cartao_pre_pago_id) REFERENCES cartao_pre_pago(id);
ALTER TABLE album_artista ADD CONSTRAINT album_artista_fk1 FOREIGN KEY (album_id) REFERENCES album(id);
ALTER TABLE album_artista ADD CONSTRAINT album_artista_fk2 FOREIGN KEY (artista_utilizador_id) REFERENCES artista(utilizador_id);
ALTER TABLE artista_musica ADD CONSTRAINT artista_musica_fk1 FOREIGN KEY (artista_utilizador_id) REFERENCES artista(utilizador_id);
ALTER TABLE artista_musica ADD CONSTRAINT artista_musica_fk2 FOREIGN KEY (musica_ismn) REFERENCES musica(ismn);
ALTER TABLE musica_album ADD CONSTRAINT musica_album_fk1 FOREIGN KEY (musica_ismn) REFERENCES musica(ismn);
ALTER TABLE musica_album ADD CONSTRAINT musica_album_fk2 FOREIGN KEY (album_id) REFERENCES album(id);




----------------ID's SEQUENCIAIS---------------------

CREATE SEQUENCE ids_utilizador;
CREATE SEQUENCE ids_album;
CREATE SEQUENCE ids_comentario;
CREATE SEQUENCE ids_playlist;
CREATE SEQUENCE ids_subscricao;
CREATE SEQUENCE ids_musica;
CREATE SEQUENCE ids_gravadora;
CREATE SEQUENCE ids_contagem_musica;
ALTER TABLE utilizador
ALTER COLUMN id SET DEFAULT nextval('ids_utilizador');
ALTER TABLE album
ALTER COLUMN id SET DEFAULT nextval('ids_album');
ALTER TABLE comentario
ALTER COLUMN id SET DEFAULT nextval('ids_comentario');
ALTER TABLE playlist
ALTER COLUMN id SET DEFAULT nextval('ids_playlist');
ALTER TABLE subscricao
ALTER COLUMN id SET DEFAULT nextval('ids_subscricao');
ALTER TABLE musica
ALTER COLUMN ismn SET DEFAULT nextval('ids_musica');
ALTER TABLE gravadora
ALTER COLUMN id SET DEFAULT nextval('ids_gravadora');
ALTER TABLE contagem_musica
ALTER COLUMN id SET DEFAULT nextval('ids_contagem_musica');




----------------------------------Trigger----------------------------------------------

BEGIN
    -- Limpar as entradas anteriores na tabela musica_playlist
    DELETE FROM musica_playlist
    WHERE playlist_id IN (
        SELECT id
        FROM playlist
        WHERE nome = 'TOP10' AND consumidor_utilizador_id = NEW.consumidor_utilizador_id
    );

    -- Selecionar as 10 músicas mais frequentes para o consumidor
    WITH top_10 AS (
        SELECT musica_ismn
        FROM contagem_musica
        WHERE consumidor_utilizador_id = NEW.consumidor_utilizador_id
        GROUP BY musica_ismn
        ORDER BY COUNT(*) DESC
        LIMIT 10
    )
    -- Inserir as entradas na tabela musica_playlist
    INSERT INTO musica_playlist (playlist_id, musica_ismn)
    SELECT p.id, t.musica_ismn
    FROM playlist p
    CROSS JOIN top_10 t
    WHERE p.nome = 'TOP10' AND p.consumidor_utilizador_id = NEW.consumidor_utilizador_id;

    RETURN NULL;
END;


CREATE  OR REPLACE TRIGGER atualizar_top_10_trigger
AFTER INSERT ON contagem_musica
FOR EACH ROW
EXECUTE FUNCTION atualizar_top_10()
