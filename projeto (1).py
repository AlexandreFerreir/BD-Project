import flask
from flask import Flask, jsonify, request
from flask_jwt_extended import JWTManager, jwt_required, create_access_token, get_jwt_identity
import logging
import psycopg2
import hashlib
import secrets
import random
import datetime

data_hoje = datetime.date.today()

app = flask.Flask(__name__)
app.config['JWT_SECRET_KEY'] = str(secrets.SystemRandom().getrandbits(128))
jwt = JWTManager(app)

StatusCodes = {
    'success': 200,
    'api_error': 400,
    'internal_error': 500
}


##########################################################
## DATABASE ACCESS
##########################################################

def ler_atributos_do_arquivo(nome_arquivo):
    atributos = []
    with open(nome_arquivo, 'r') as arquivo:
        for linha in arquivo:
            atributos.append(linha.strip())
    arquivo.close()
    return atributos


def db_connection():
    lista = ler_atributos_do_arquivo("config.txt")
    db = psycopg2.connect(
        user=lista[0],
        password=lista[1],
        host=lista[2],
        port=lista[3],
        database=lista[4]
    )
    return db


def ponto_virgula_recursivo(rec):
    if isinstance(rec, list):
        for i in rec:
            ponto_virgula_recursivo(i)
    else:
        if ";" in rec:
            return 1


def check_payload(payload):
    for chave in payload:
        if ponto_virgula_recursivo(payload[chave]) == 1:
            return 1
    return 0


@app.route('/report/<year_month>', methods=['GET'])
@jwt_required()
def generate_monthly_report(year_month):
    logger.info(f'GET /report/{year_month}')

    if ";" in year_month:
        response = {'status': StatusCodes['api_error'], 'results': 'Fields cannot contain ";"'}
        return flask.jsonify(response)

    conn = db_connection()
    cur = conn.cursor()

    try:
        cur.execute('BEGIN')
        cur.execute('LOCK TABLE contagem_musica,musica IN EXCLUSIVE MODE')
        # recebe dois parâmetros: N (número de resultados desejados) e year_month (ano e mês no formato 'YYYY-MM'). CUIDADO PROTEGER!!!!!!!!!
        # Extrair o ano e mês da string year_month
        year = int(year_month.split('-')[0])
        month = int(year_month.split('-')[1])

        # Calcular a data inicial e final do período de 12 meses
        start_date = datetime.date(year, month, 1)
        end_date = datetime.date(year - 1, month, 1)

        # Consulta para obter o número de músicas reproduzidas por mês e genero
        query = f'''
            SELECT
                to_char(cm.data, 'YYYY-MM') AS date,
                m.genero AS genre,
                COUNT(*) AS playbacks
            FROM
                contagem_musica cm
            INNER JOIN
                musica m ON cm.musica_ismn = m.ismn
            WHERE
                cm.data BETWEEN '{end_date}' AND '{start_date}'
            GROUP BY
                date, genre
            ORDER BY
                date, playbacks DESC
                ;
        '''
        cur.execute(query)
        rows = cur.fetchall()
        print(rows)

        # Formatar os resultados
        results = []
        for row in rows:
            result = {
                'month': str(row[0]).split("-")[1],
                'genre': row[1],
                'playbacks': row[2]
            }
            results.append(result)

        response = {'status': StatusCodes['success'], 'results': results}
        # cur.execute('UNLOCK TABLE contagem_musica,musica IN EXCLUSIVE MODE')
        conn.commit()

    except (Exception, psycopg2.DatabaseError) as error:
        logger.error(f'GET /report/{year_month} - error: {error}')
        response = {'status': StatusCodes['internal_error'], 'errors': str(error)}
        conn.rollback()

    finally:
        if conn is not None:
            conn.close()

    return flask.jsonify(response)


@app.route('/artist_info/<artist_id>', methods=['GET'])
@jwt_required()
def detail_artist(artist_id):
    logger.info(f'GET/artist_info/{artist_id}')
    if ";" in artist_id:
        response = {'status': StatusCodes['api_error'], 'results': 'Fields cannot contain ";"'}
        return flask.jsonify(response)

    conn = db_connection()
    cur = conn.cursor()

    try:
        cur.execute('BEGIN')
        cur.execute('LOCK TABLE artista,musica,album IN EXCLUSIVE MODE')
        # Consulta para obter as informações do artista
        query = """
        SELECT
            a.nome AS nome,
            ARRAY_AGG(DISTINCT m.ismn) AS musicas,
            ARRAY_AGG(DISTINCT al.id) AS albums,
            ARRAY_AGG(DISTINCT p.id) AS playlists
        FROM artista AS a
        LEFT JOIN artista_musica AS am ON am.artista_utilizador_id = a.utilizador_id
        LEFT JOIN musica AS m ON m.ismn = am.musica_ismn
        LEFT JOIN album_artista AS aa ON aa.artista_utilizador_id = a.utilizador_id
        LEFT JOIN album AS al ON al.id = aa.album_id
        LEFT JOIN musica_playlist AS mp ON mp.musica_ismn = m.ismn
        LEFT JOIN playlist AS p ON p.id = mp.playlist_id and p.visibilidade=true
        WHERE a.utilizador_id = %s
        GROUP BY a.utilizador_id;
        """
        cur.execute(query, (artist_id,))
        row = cur.fetchone()

        if row is not None:
            artist_info = {
                'name': row[0],
                'songs': row[1] if row[1] != [None] else "No results",
                'albums': row[2] if row[2] != [None] else "No results",
                'playlists': row[3] if row[3] != [None] else "No results"
            }
            response = {'status': StatusCodes['success'], 'results': artist_info}
        else:
            response = {'status': StatusCodes['success'], 'results': 'No results'}

        conn.commit()

    except (Exception, psycopg2.Error) as error:
        logger.error(f'GET /artist_info/{artist_id} - error: {error}')
        response = {'status': StatusCodes['internal_error'], 'errors': str(error)}
        conn.rollback()

    finally:
        if conn is not None:
            conn.close()

    return flask.jsonify(response)


@app.route('/add_album', methods=['POST'])
@jwt_required()
def add_album():
    user_payload = get_jwt_identity()
    if (user_payload['type'] == "artista"):
        logger.info('POST /add_album')
        payload = flask.request.get_json()

        conn = db_connection()
        cur = conn.cursor()

        logger.debug(f'POST /add_album - payload: {payload}')

        # Validar os campos obrigatórios
        if 'name' not in payload or 'release_date' not in payload or 'publisher' not in payload or 'songs' not in payload:
            response = {'status': StatusCodes['api_error'], 'results': 'Missing required field'}
            return flask.jsonify(response)

        if check_payload(payload):
            response = {'status': StatusCodes['api_error'], 'results': 'Fields cannot contain ";"'}
            return flask.jsonify(response)

        statement = 'INSERT INTO album (titulo, data_de_lancamento,gravadora_id) VALUES (%s, %s,%s) RETURNING id'
        values = (payload['name'], payload['release_date'], payload['publisher'])

        try:
            cur.execute("BEGIN")
            cur.execute('LOCK TABLE album,musica,artista_musica,musica_album,album_artista IN EXCLUSIVE MODE')
            # conn.begin()
            # Inserir o álbum
            cur.execute(statement, values)
            album_id = cur.fetchone()[0]

            # Inserir as músicas do álbum
            songs = payload['songs']
            for song in songs:
                if isinstance(song, dict):
                    if 'name' not in song or 'type' not in song or 'duration' not in song or 'release_date' not in song or 'publisher' not in song:
                        response = {'status': StatusCodes['api_error'],
                                    'results': 'Missing required fields to create a new music'}
                        conn.rollback()
                        return flask.jsonify(response)

                    if check_payload(song):
                        response = {'status': StatusCodes['api_error'],
                                    'results': 'Fields cannot contain ";"'}
                        conn.rollback()
                        return flask.jsonify(response)

                    # Nova música
                    other_artists = song.get('other_artists', [])

                    # Inserir a música
                    cur.execute(
                        'INSERT INTO musica (titulo,genero,duracao,data_de_lancamento, gravadora_id) VALUES (%s, %s, %s, %s, %s) RETURNING ismn',
                        (song.get('name'), song.get('type'), song.get('duration'), song.get('release_date'),
                         song.get('publisher')))
                    song_id = cur.fetchone()[0]
                    other_artists = [user_payload['id']] + other_artists
                    # Inserir os relacionamentos entre a música e os outros artistas na tabela "artista_musica"
                    if other_artists:
                        values_artists = [(artist_id, song_id) for artist_id in other_artists]
                        cur.executemany(
                            'INSERT INTO artista_musica (artista_utilizador_id,musica_ismn) VALUES (%s, %s)',
                            values_artists)

                    # Inserir o relacionamento entre a música e o álbum na tabela "musica_album"
                    cur.execute('INSERT INTO musica_album (musica_ismn,album_id) VALUES (%s, %s)', (song_id, album_id))
                else:
                    # Música existente (identificador)
                    song_id = song

                    if ";" in song_id:
                        response = {'status': StatusCodes['api_error'],
                                    'results': 'Fields cannot contain ";"'}
                        conn.rollback()
                        return flask.jsonify(response)

                    # Verificar se a música existe na plataforma
                    cur.execute('SELECT COUNT(*) FROM musica WHERE ismn = %s', (song_id,))
                    count = cur.fetchone()[0]
                    if count == 0:
                        response = {'status': StatusCodes['api_error'],
                                    'results': f'Give song {song_id} does not exist'}
                        conn.rollback()
                        return flask.jsonify(response)

                    # Inserir o relacionamento entre a música existente e o álbum na tabela "musica_album"
                    cur.execute('INSERT INTO musica_album (musica_ismn,album_id) VALUES (%s, %s)', (song_id, album_id))

            cur.execute('INSERT INTO album_artista (album_id, artista_utilizador_id) VALUES (%s, %s)',
                        (album_id, user_payload['id']))
            conn.commit()
            response = {'status': StatusCodes['success'], 'results': album_id}

        except (Exception, psycopg2.DatabaseError) as error:
            logger.error(f'POST /add_album - error: {error}')
            response = {'status': StatusCodes['internal_error'], 'errors': str(error)}
            conn.rollback()

        finally:
            if conn is not None:
                conn.close()

        return flask.jsonify(response)
    else:
        response = {'status': StatusCodes['api_error'],
                    'results': 'This user does not have the permission to add albums'}
        return flask.jsonify(response)


@app.route('/<song>', methods=['PUT'])
@jwt_required()
def play_song(song):
    user_payload = get_jwt_identity()
    if (user_payload['type'] == "consumidor"):
        logger.info(f'PUT / {song}')

        if ";" in song:
            response = {'status': StatusCodes['api_error'], 'results': 'Fields cannot contain ";"'}
            return flask.jsonify(response)

        conn = db_connection()
        cur = conn.cursor()

        logger.debug(f'song_id: {song}')

        try:
            cur.execute('BEGIN')
            cur.execute('LOCK TABLE contagem_musica,musica IN EXCLUSIVE MODE')

            cur.execute('SELECT titulo FROM musica WHERE ismn=%s', (song,))
            flag = cur.fetchone()
            if (flag != None):

                values = (data_hoje, user_payload['id'], song)
                cur.execute(
                    'INSERT INTO contagem_musica (data,consumidor_utilizador_id,musica_ismn) VALUES (%s,%s,%s)',
                    values)

                conn.commit()
                response = {'status': StatusCodes['success'], 'results': "sucess"}
            else:
                response = {'status': StatusCodes['api_error'], 'results': 'Given song does not exist'}
                conn.rollback()
                return flask.jsonify(response)




        except (Exception, psycopg2.DatabaseError) as error:
            logger.error(f'PUT /{song} - error: {error}')
            response = {'status': StatusCodes['internal_error'], 'errors': str(error)}
            conn.rollback()

        finally:
            if conn is not None:
                conn.close()

        return flask.jsonify(response)

    else:
        response = {'status': StatusCodes['api_error'], 'results': 'Only consumers can play a song'}
        return flask.jsonify(response)


@app.route('/comment/<song_id>/<parent_id_comment>', methods=['POST'])
@app.route('/comment/<song_id>', methods=['POST'])
@jwt_required()
def make_comment(song_id, parent_id_comment=None):
    user_payload = get_jwt_identity()
    if (user_payload['type'] == "consumidor"):
        logger.info('POST /comment')
        payload = flask.request.get_json()

        conn = db_connection()
        cur = conn.cursor()

        logger.debug(f'song_id: {song_id}, parent_id_comment: {parent_id_comment}')
        if ";" in song_id:
            response = {'status': StatusCodes['api_error'], 'results': 'Fields cannot contain ";"'}
            return flask.jsonify(response)

        if parent_id_comment is not None:
            if ";" in parent_id_comment:
                response = {'status': StatusCodes['api_error'], 'results': 'Fields cannot contain ";"'}
                return flask.jsonify(response)

        logger.debug(f'POST /comment - payload: {payload}')

        # Validar os campos obrigatórios
        if 'comment' not in payload:
            response = {'status': StatusCodes['api_error'], 'results': 'Missing required field'}
            return flask.jsonify(response)

        if check_payload(payload):
            response = {'status': StatusCodes['api_error'], 'results': 'Fields cannot contain ";"'}
            return flask.jsonify(response)

        try:
            cur.execute('BEGIN')
            cur.execute('LOCK TABLE comentario,comentario_comentario IN EXCLUSIVE MODE')

            cur.execute('SELECT ismn FROM musica WHERE ismn=%s', (song_id,))

            if cur.fetchone() is None:
                response = {'status': StatusCodes['api_error'],
                            'results': 'Given song does not exist'}
                conn.rollback()
                return flask.jsonify(response)

            if (parent_id_comment != None):
                cur.execute('SELECT musica_ismn FROM comentario WHERE id=%s', (parent_id_comment,))
                musica = cur.fetchone()
                if musica is None:
                    response = {'status': StatusCodes['api_error'],
                                'results': 'Given comment does not exist'}
                    conn.rollback()
                    return flask.jsonify(response)

                if (musica[0] != int(song_id)):
                    response = {'status': StatusCodes['api_error'],
                                'results': 'Given comment does not refer to given song'}
                    conn.rollback()
                    return flask.jsonify(response)

            values = (payload['comment'], data_hoje, song_id, user_payload['id'])
            cur.execute(
                'INSERT INTO comentario (texto,data_de_criacao,musica_ismn,consumidor_utilizador_id) VALUES (%s,%s,%s,%s) RETURNING id',
                values)
            id_novo_comentario = cur.fetchone()[0]

            if (parent_id_comment != None):
                values = (parent_id_comment, id_novo_comentario)
                cur.execute(
                    'INSERT INTO comentario_comentario (comentario_id,comentario_id1) VALUES (%s,%s)',
                    values)

            conn.commit()
            response = {'status': StatusCodes['success'], 'results': id_novo_comentario}

        except (Exception, psycopg2.DatabaseError) as error:
            logger.error(f'POST /add_playlist - error: {error}')
            response = {'status': StatusCodes['internal_error'], 'errors': str(error)}
            conn.rollback()

        finally:
            if conn is not None:
                conn.close()

        return flask.jsonify(response)


    else:
        response = {'status': StatusCodes['api_error'], 'results': 'Only consumers can comment'}
        return flask.jsonify(response)


def traduz_visibilidade(visibility):
    if (visibility == "public"):
        return True
    else:
        return False


def procura_tipo_de_plano(consulta):
    data_de_validade = None
    for linha in consulta:
        if linha[0] is None:
            temp = "Regular"
        elif data_hoje < linha[0]:
            temp = "Premium"
            data_de_validade = linha[0]

    return temp, data_de_validade


@app.route('/add_playlist', methods=['POST'])
@jwt_required()
def create_playlist():
    user_payload = get_jwt_identity()
    if (user_payload['type'] == "consumidor"):
        logger.info('POST /add_playlist')
        payload = flask.request.get_json()

        conn = db_connection()
        cur = conn.cursor()

        logger.debug(f'POST /add_playlist - payload: {payload}')

        # Validar os campos obrigatórios
        if 'playlist_name' not in payload or 'visibility' not in payload or 'songs' not in payload:
            response = {'status': StatusCodes['api_error'], 'results': 'Missing required fields'}
            return flask.jsonify(response)

        if check_payload(payload):
            response = {'status': StatusCodes['api_error'], 'results': 'Fields cannot contain ";"'}
            return flask.jsonify(response)

        if payload['playlist_name'] == "TOP10":
            response = {'status': StatusCodes['api_error'], 'results': 'Playlist name "TOP10" not allowed'}
            return flask.jsonify(response)

        try:
            cur.execute('BEGIN')
            cur.execute('LOCK TABLE subscricao,playlist,musica_playlist IN EXCLUSIVE MODE')

            cur.execute('SELECT data_de_validade FROM subscricao WHERE consumidor_utilizador_id=%s',
                        (user_payload['id'],))

            consulta = cur.fetchall()
            tipo_de_plano, data_de_validade = procura_tipo_de_plano(consulta)
            if (tipo_de_plano == "Premium"):
                values = (payload['playlist_name'], traduz_visibilidade(payload['visibility']), user_payload['id'])
                cur.execute(
                    'INSERT INTO playlist (nome,visibilidade,consumidor_utilizador_id) VALUES (%s,%s,%s) RETURNING id',
                    values)
                id_playlist = cur.fetchone()[0]

                for song in payload['songs']:
                    values = (song, id_playlist)
                    cur.execute('INSERT INTO musica_playlist (musica_ismn,playlist_id) VALUES (%s,%s)', values)

                response = {'status': StatusCodes['success'], 'results': id_playlist}

            else:
                response = {'status': StatusCodes['api_error'],
                            'results': 'Only premium consumers can create a playlist'}
                conn.rollback()
                return flask.jsonify(response)

            conn.commit()



        except (Exception, psycopg2.DatabaseError) as error:
            logger.error(f'POST /add_playlist - error: {error}')
            response = {'status': StatusCodes['internal_error'], 'errors': str(error)}
            conn.rollback()

        finally:
            if conn is not None:
                conn.close()

        return flask.jsonify(response)

    else:
        response = {'status': StatusCodes['api_error'], 'results': 'Only consumers can create a playlist'}
        return flask.jsonify(response)


@app.route('/card', methods=['POST'])
@jwt_required()
def generate_card():
    user_payload = get_jwt_identity()
    if (user_payload['type'] == "administrador"):
        logger.info('POST /card')
        payload = flask.request.get_json()

        conn = db_connection()
        cur = conn.cursor()

        logger.debug(f'POST /card - payload: {payload}')

        # Validar os campos obrigatórios
        if 'number_cards' not in payload or 'card_price' not in payload:
            response = {'status': StatusCodes['api_error'], 'results': 'Missing required fields'}
            return flask.jsonify(response)

        if check_payload(payload):
            response = {'status': StatusCodes['api_error'], 'results': 'Fields cannot contain ";"'}
            return flask.jsonify(response)

        aux = ["10", "25", "50"]

        if payload['card_price'] not in aux:
            response = {'status': StatusCodes['api_error'], 'results': 'Card price can only be 10, 25 or 50'}
            return flask.jsonify(response)

        try:
            ids = []
            cur.execute('BEGIN')
            cur.execute('LOCK TABLE cartao_pre_pago IN EXCLUSIVE MODE')
            for i in range(int(payload['number_cards'])):
                var = 1
                while (var):
                    identity = generate_random_sequence()
                    cur.execute('SELECT * FROM cartao_pre_pago WHERE id=%s', (identity,))
                    if (cur.fetchone() is None):
                        var = 0

                # print(identity)
                values = (identity, payload['card_price'],
                          datetime.date(int(str(data_hoje).split("-")[0]) + 1, int(str(data_hoje).split("-")[1]),
                                        int(str(data_hoje).split("-")[2])), payload['card_price'], user_payload['id'])
                cur.execute(
                    'INSERT INTO cartao_pre_pago (id,valor,data_de_validade,valor_restante,administrador_utilizador_id) VALUES (%s,%s,%s,%s,%s)',
                    values)
                ids += [identity]

            conn.commit()
            response = {'status': StatusCodes['success'], 'results': ids}

        except (Exception, psycopg2.DatabaseError) as error:
            logger.error(f'POST /card - error: {error}')
            response = {'status': StatusCodes['internal_error'], 'errors': str(error)}
            conn.rollback()

        finally:
            if conn is not None:
                conn.close()

        return flask.jsonify(response)

    else:
        response = {'status': StatusCodes['api_error'], 'results': 'Only admins can generate a card'}
        return flask.jsonify(response)


def soma_datas(data, periodo):
    dicio = {'month': 1, 'quarter': 3, 'semester': 6}
    periodo = dicio[periodo]
    if (int(data.split('-')[1]) + periodo > 12):
        final = datetime.date(int(data.split('-')[0]) + 1, int(data.split('-')[1]) + periodo - 12,
                              int(data.split('-')[2]))
    else:
        final = datetime.date(int(data.split('-')[0]), int(data.split('-')[1]) + periodo, int(data.split('-')[2]))
    return final


@app.route('/subscribe', methods=['POST'])
@jwt_required()
def subscription():
    user_payload = get_jwt_identity()
    if (user_payload['type'] == "consumidor"):
        logger.info('POST /subscribe')
        payload = flask.request.get_json()

        conn = db_connection()
        cur = conn.cursor()

        logger.debug(f'POST /subscribe - payload: {payload}')

        # Validar os campos obrigatórios
        if 'period' not in payload or 'cards' not in payload:
            response = {'status': StatusCodes['api_error'], 'results': 'Missing required fields'}
            return flask.jsonify(response)

        if check_payload(payload):
            response = {'status': StatusCodes['api_error'], 'results': 'Fields cannot contain ";"'}
            return flask.jsonify(response)

        aux = ["month", "quarter", "semester"]

        if payload['period'] not in aux:
            response = {'status': StatusCodes['api_error'], 'results': 'Period can only be month, quarter or semester'}
            return flask.jsonify(response)

        try:
            cur.execute('BEGIN')
            cur.execute('LOCK TABLE cartao_pre_pago,subscricao,subscricao_cartao_pre_pago IN EXCLUSIVE MODE')

            dicio = {'month': 7, 'quarter': 21, 'semester': 42}
            total = 0
            cartoes = []
            for card in payload['cards']:
                cur.execute('SELECT data_de_validade,valor_restante FROM cartao_pre_pago WHERE id=%s', (card,))
                linha = cur.fetchone()
                if data_hoje <= linha[0] and int(linha[1]) > 0 and total < dicio[payload['period']]:
                    total += int(linha[1])
                    cartoes += [[card, int(linha[1])]]
            total2 = 0
            if (total >= dicio[payload['period']]):

                for cartao in cartoes:
                    total2 += cartao[1]
                    if (total2 != total):
                        cur.execute('UPDATE cartao_pre_pago SET valor_restante = %s WHERE id=%s', (0, cartao[0],))
                    else:
                        cur.execute('UPDATE cartao_pre_pago SET valor_restante = %s WHERE id=%s',
                                    (total - dicio[payload['period']], cartao[0],))

            else:
                response = {'status': StatusCodes['api_error'],
                            'results': 'Given card(s) not enough to pay the subscription'}
                conn.rollback()
                return flask.jsonify(response)

            cur.execute('SELECT data_de_validade FROM subscricao WHERE consumidor_utilizador_id=%s',
                        (user_payload['id'],))

            consulta = cur.fetchall()
            tipo_de_plano, data_de_validade = procura_tipo_de_plano(consulta)
            id_subscricao = ""

            if (tipo_de_plano == 'Regular'):
                statement = 'INSERT INTO subscricao (tipo_de_plano,data_de_inicio,data_de_validade,consumidor_utilizador_id) VALUES (%s, %s, %s, %s) RETURNING id;'
                values = ('Premium', data_hoje, soma_datas(str(data_hoje), payload['period']), user_payload['id'])
                cur.execute(statement, values)
                id_subscricao = cur.fetchone()[0]

            elif (tipo_de_plano == 'Premium'):
                statement = 'INSERT INTO subscricao (tipo_de_plano,data_de_inicio,data_de_validade,consumidor_utilizador_id) VALUES (%s, %s, %s, %s)RETURNING id;'
                values = (
                'Premium', data_de_validade, soma_datas(str(data_de_validade), payload['period']), user_payload['id'])
                cur.execute(statement, values)
                id_subscricao = cur.fetchone()[0]

            for cartao in cartoes:
                cur.execute('INSERT INTO subscricao_cartao_pre_pago (subscricao_id,cartao_pre_pago_id) VALUES (%s,%s)',
                            (id_subscricao, cartao[0],))

            conn.commit()

            response = {'status': StatusCodes['success'], 'results': id_subscricao}

        except (Exception, psycopg2.DatabaseError) as error:
            logger.error(f'GET /subscribe - error: {error}')
            response = {'status': StatusCodes['internal_error'], 'errors': str(error)}
            conn.rollback()

        finally:
            if conn is not None:
                conn.close()

        return flask.jsonify(response)

    else:
        response = {'status': StatusCodes['api_error'], 'results': 'Only consumers can make a subscription'}
        return flask.jsonify(response)


def generate_random_sequence():
    sequence = ''.join(random.choices('0123456789', k=16))
    return str(sequence)


def formata_search_song(consulta):
    saida = []
    linha = ["", [], []]

    for i in range(len(consulta)):
        if consulta[i][0] != linha[0]:
            if (i != 0):
                saida += [linha]
            linha = [consulta[i][0], [consulta[i][1]], [consulta[i][2]]]
            if (i == len(consulta) - 1):
                saida += [linha]
        else:
            if consulta[i][1][0] != linha[1][0]:
                linha[1] += [consulta[i][1]]
                if (i == len(consulta) - 1):
                    saida += [linha]
            else:
                if consulta[i][2][0] != linha[2][0]:
                    if consulta[i][2] is not None:
                        linha[2] += [consulta[i][2]]
                    if i == len(consulta) - 1:
                        saida += [linha]
    res = []
    for elemento in saida:
        resultados = {
            "song_title": elemento[0],
            "artists": elemento[1] if elemento[1] != [None] else "No results",
            "albuns": elemento[2] if elemento[2] != [None] else "No results"
        }
        res.append(resultados)
    return res


@app.route('/search_song/<keyword>', methods=['GET'])
@jwt_required()
def search_song(keyword):
    logger.info('GET /search_song/<keyword>')

    logger.debug(f'keyword: {keyword}')

    if ";" in keyword:
        response = {'status': StatusCodes['api_error'], 'results': 'Fields cannot contain ";"'}
        return flask.jsonify(response)

    conn = db_connection()
    cur = conn.cursor()

    try:
        cur.execute('BEGIN')
        cur.execute('LOCK TABLE musica,artista,artista_musica,album,musica_album IN EXCLUSIVE MODE')

        cur.execute('SELECT m.titulo AS nome_musica, a.nome_artistico, al.id '
                    'FROM musica AS m '
                    'LEFT JOIN artista_musica AS am ON m.ismn = am.musica_ismn '
                    'LEFT JOIN artista AS a ON am.artista_utilizador_id = a.utilizador_id '
                    'LEFT JOIN musica_album AS ma ON m.ismn = ma.musica_ismn '
                    'LEFT JOIN album AS al ON ma.album_id = al.id '
                    'WHERE m.titulo LIKE %s', (f"%{keyword}%",))

        consulta = cur.fetchall()
        # print(consulta)
        response = {'status': StatusCodes['success'], 'results': formata_search_song(consulta)}
        conn.commit()

    except (Exception, psycopg2.DatabaseError) as error:
        logger.error(f'GET /search_song - error: {error}')
        response = {'status': StatusCodes['internal_error'], 'errors': str(error)}
        conn.rollback()

    finally:
        if conn is not None:
            conn.close()

    return flask.jsonify(response)


@app.route('/teste', methods=['GET'])
@jwt_required()
def teste1():
    response = "permission granted"
    response += ' ' + get_jwt_identity()['type']
    return flask.jsonify(response)


@app.route('/add_song', methods=['POST'])
@jwt_required()
def add_song():
    user_payload = get_jwt_identity()
    if (user_payload['type'] == "artista"):
        logger.info('POST /add_song')
        payload = flask.request.get_json()

        conn = db_connection()
        cur = conn.cursor()

        logger.debug(f'POST /add_song - payload: {payload}')

        # Validar os campos obrigat贸rios
        if 'name' not in payload or 'release_date' not in payload or 'publisher' not in payload or 'type' not in payload or 'duration' not in payload:
            response = {'status': StatusCodes['api_error'], 'results': 'Missing required fields'}
            return flask.jsonify(response)

        if check_payload(payload):
            response = {'status': StatusCodes['api_error'], 'results': 'Fields cannot contain ";"'}
            return flask.jsonify(response)

        statement = 'INSERT INTO musica (titulo,genero,duracao,data_de_lancamento, gravadora_id) VALUES (%s, %s, %s, %s, %s) RETURNING ismn'
        values = (payload['name'], payload['type'], payload['duration'],
                  payload['release_date'], payload['publisher'])
        other_artists = payload.get('other_artists', [])
        try:
            cur.execute('BEGIN')
            cur.execute('LOCK TABLE artista_musica,musica IN EXCLUSIVE MODE')
            # conn.begin()
            # Inserir a música
            cur.execute(statement, values)
            musica_id = cur.fetchone()[0]
            if str(user_payload['id']) in other_artists:
                conn.rollback()
                response = {'status': StatusCodes['api_error'],
                            'results': 'Given artists can not include the user id'}
                return flask.jsonify(response)
            other_artists = [user_payload['id']] + other_artists
            # Inserir os relacionamentos entre a música e os outros artistas na tabela "artista_musica"
            if other_artists:
                values_artists = [(musica_id, artist_id) for artist_id in other_artists]
                cur.executemany('INSERT INTO artista_musica (musica_ismn, artista_utilizador_id) VALUES (%s, %s)',
                                values_artists)

            conn.commit()
            response = {'status': StatusCodes['success'], 'results': musica_id}

        except (Exception, psycopg2.DatabaseError) as error:
            logger.error(f'POST /add_song - error: {error}')
            response = {'status': StatusCodes['internal_error'], 'errors': str(error)}
            conn.rollback()

        finally:
            if conn is not None:
                conn.close()

        return flask.jsonify(response)
    else:
        response = {'status': StatusCodes['api_error'],
                    'results': 'This user does not have the permission to add songs'}
        return flask.jsonify(response)


@app.route('/login', methods=['POST'])
def authentication():
    logger.info('POST /login ')
    payload = flask.request.get_json()

    conn = db_connection()
    cur = conn.cursor()

    logger.debug(f'POST /login - payload: {payload}')

    if ('username' not in payload) or ('password' not in payload):
        response = {'status': StatusCodes['api_error'], 'results': 'required login arguments'}
        return flask.jsonify(response)

    if check_payload(payload):
        response = {'status': StatusCodes['api_error'], 'results': 'Fields cannot contain ";"'}
        return flask.jsonify(response)

    try:
        cur.execute('BEGIN')
        cur.execute('LOCK TABLE utilizador,artista,consumidor,administrador IN EXCLUSIVE MODE')

        cur.execute('SELECT palavra_passe,id FROM utilizador WHERE username=%s', (payload['username'],))
        result = cur.fetchone()
        if result is not None:
            hash_result = result[0]
            id_user = result[1]
            passe_hash = hashlib.sha256(payload['password'].encode('utf-8')).hexdigest()
            if (passe_hash == hash_result):
                cur.execute(
                    "SELECT 'consumidor' AS tipo FROM consumidor, utilizador WHERE utilizador.username = %s AND utilizador.palavra_passe = %s AND consumidor.utilizador_id = utilizador.id "
                    "UNION ALL "
                    "SELECT 'artista' AS tipo FROM artista, utilizador WHERE utilizador.username = %s AND utilizador.palavra_passe = %s AND artista.utilizador_id = utilizador.id "
                    "UNION ALL "
                    "SELECT 'administrador' AS tipo FROM administrador, utilizador WHERE utilizador.username = %s AND utilizador.palavra_passe = %s AND administrador.utilizador_id = utilizador.id",
                    (
                        payload['username'], passe_hash, payload['username'], passe_hash, payload['username'],
                        passe_hash))

                tipo = cur.fetchone()[0]
                payload['type'] = tipo
                payload['id'] = id_user

                '''statement = 'CREATE OR REPLACE FUNCTION atualizar_top_10() ' \
                            'RETURNS TRIGGER AS $$ ' \
                            'BEGIN ' \
                            '-- Limpar as entradas anteriores na tabela musica_playlist\n ' \
                            'DELETE FROM musica_playlist ' \
                            'WHERE playlist_id = ( ' \
                            'SELECT id ' \
                            'FROM playlist ' \
                            'WHERE nome = %s AND consumidor_utilizador_id = NEW.consumidor_utilizador_id ' \
                            'LIMIT 1 ' \
                            '); ' \
                            '-- Selecionar as 10 músicas mais frequentes para o consumidor\n ' \
                            'WITH top_10 AS ( ' \
                            'SELECT ismn_musica, COUNT(*) AS total ' \
                            'FROM contagem_musica ' \
                            'WHERE consumidor_utilizador_id = NEW.consumidor_utilizador_id ' \
                            'GROUP BY ismn_musica ' \
                            'ORDER BY total DESC ' \
                            'LIMIT 10 ' \
                            ') ' \
                            '-- Inserir as entradas na tabela musica_playlist \n' \
                            'INSERT INTO musica_playlist (musica_id, playlist_id) ' \
                            'SELECT c.ismn_musica, p.id ' \
                            'FROM top_10 t ' \
                            'CROSS JOIN playlist p ' \
                            'WHERE p.nome = %s AND p.consumidor_utilizador_id = NEW.consumidor_utilizador_id; ' \
                            'RETURN NULL; ' \
                            'END; ' \
                            '$$ LANGUAGE plpgsql;'
                values = ("TOP10", "TOP10")
                cur.execute(statement, values)

                statement = 'CREATE TRIGGER atualizar_top_10_trigger ' \
                            'AFTER INSERT ON contagem_musica ' \
                            'FOR EACH ROW ' \
                            'EXECUTE FUNCTION atualizar_top_10();'
                cur.execute(statement)'''

                response = {'status': StatusCodes['success'], 'results': create_access_token(identity=payload)}
                conn.commit()
            else:
                response = {'status': StatusCodes['api_error'], 'results': 'Login credentials not valid'}
                conn.rollback()
                return flask.jsonify(response)
        else:
            response = {'status': StatusCodes['api_error'], 'results': 'User does not exist'}
            conn.rollback()
            return flask.jsonify(response)

    except (Exception, psycopg2.DatabaseError) as error:
        logger.error(f'POST /login - error: {error}')
        response = {'status': StatusCodes['internal_error'], 'errors': str(error)}
        conn.rollback()

    finally:
        if conn is not None:
            conn.close()

    return flask.jsonify(response)


@app.route('/create', methods=['POST'])
@jwt_required(optional=True)
def add_user():
    user_payload = get_jwt_identity()
    if user_payload is None:
        logger.info('POST /create ')
        payload = flask.request.get_json()

        conn = db_connection()
        cur = conn.cursor()

        logger.debug(f'POST /create - payload: {payload}')

        if ('username' not in payload) or ('password' not in payload) or ('nome' not in payload) or (
                'endereco' not in payload) or ('data de nascimento' not in payload) or ('contacto' not in payload):
            response = {'status': StatusCodes['api_error'], 'results': 'required create fields'}
            return flask.jsonify(response)

        if check_payload(payload):
            response = {'status': StatusCodes['api_error'], 'results': 'Fields cannot contain ";"'}
            return flask.jsonify(response)

        statement = 'INSERT INTO utilizador (username,palavra_passe) VALUES (%s, %s) RETURNING id;'
        values = (payload['username'], hashlib.sha256(payload['password'].encode('utf-8')).hexdigest())

        try:
            cur.execute('BEGIN')
            cur.execute('LOCK TABLE utilizador,subscricao,consumidor,playlist IN EXCLUSIVE MODE')

            cur.execute(statement, values)
            cur.execute("SELECT lastval()")
            id_utilizador = cur.fetchone()[0]

            # commit the transaction
            # conn.commit()

            statement = 'INSERT INTO consumidor (nome,endereco,data_de_nascimento,informacoes_de_contacto,utilizador_id) VALUES (%s, %s, %s, %s, %s)'
            values = (payload['nome'], payload['endereco'], payload['data de nascimento'], payload['contacto'],
                      id_utilizador)
            cur.execute(statement, values)

            statement = 'INSERT INTO subscricao (tipo_de_plano,data_de_inicio,data_de_validade,consumidor_utilizador_id) VALUES (%s, %s, %s, %s)'
            values = ("Regular", None, None,
                      id_utilizador)
            cur.execute(statement, values)

            statement = 'INSERT INTO playlist (nome,visibilidade,consumidor_utilizador_id) VALUES (%s, %s, %s)'
            values = ("TOP10", False, id_utilizador)
            cur.execute(statement, values)

            conn.commit()

            response = {'status': StatusCodes['success'], 'results': f'Inserted user {id_utilizador}'}


        except (Exception, psycopg2.DatabaseError) as error:
            logger.error(f'POST /create - error: {error}')
            response = {'status': StatusCodes['internal_error'], 'errors': str(error)}

            # an error occurred, rollback
            conn.rollback()

        finally:
            if conn is not None:
                conn.close()

        return flask.jsonify(response)

    else:
        if (user_payload['type'] == "administrador"):

            logger.info('POST /create ')
            payload = flask.request.get_json()

            conn = db_connection()
            cur = conn.cursor()

            logger.debug(f'POST /create - payload: {payload}')

            if ('username' not in payload) or ('password' not in payload) or ('nome' not in payload) or (
                    'nome artistico' not in payload) or ('endereco' not in payload) or (
                    'data de nascimento' not in payload) or ('contacto' not in payload):
                response = {'status': StatusCodes['api_error'], 'results': 'required create fields'}
                return flask.jsonify(response)

            if check_payload(payload):
                response = {'status': StatusCodes['api_error'], 'results': 'Fields cannot contain ";"'}
                return flask.jsonify(response)

            statement = 'INSERT INTO utilizador (username,palavra_passe) VALUES (%s, %s) RETURNING id;'
            values = (payload['username'], hashlib.sha256(payload['password'].encode('utf-8')).hexdigest())

            try:
                cur.execute('BEGIN')
                cur.execute('LOCK TABLE utilizador,artista IN EXCLUSIVE MODE')

                cur.execute(statement, values)
                cur.execute("SELECT lastval()")
                id_utilizador = cur.fetchone()[0]

                # commit the transaction
                # conn.commit()

                statement = 'INSERT INTO artista (nome,nome_artistico,endereco,data_de_nascimento,informacoes_de_contacto,administrador_utilizador_id,utilizador_id) VALUES (%s, %s, %s, %s, %s, %s, %s)'
                values = (
                payload['nome'], payload['nome artistico'], payload['endereco'], payload['data de nascimento'],
                payload['contacto'], user_payload['id'],
                id_utilizador)
                cur.execute(statement, values)

                conn.commit()

                response = {'status': StatusCodes['success'], 'results': f'Inserted artist {id_utilizador}'}


            except (Exception, psycopg2.DatabaseError) as error:
                logger.error(f'POST /create - error: {error}')
                response = {'status': StatusCodes['internal_error'], 'errors': str(error)}

                # an error occurred, rollback
                conn.rollback()

            finally:
                if conn is not None:
                    conn.close()

            return flask.jsonify(response)

        else:
            response = {'status': StatusCodes['api_error'], 'results': 'Only admins can create artists'}
            return flask.jsonify(response)


if __name__ == '__main__':
    # set up logging
    logging.basicConfig(filename='log_file.log')
    logger = logging.getLogger('logger')
    logger.setLevel(logging.DEBUG)
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)

    # create formatter
    formatter = logging.Formatter('%(asctime)s [%(levelname)s]:  %(message)s', '%H:%M:%S')
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    host = '127.0.0.1'
    port = 8080
    app.run(host=host, debug=True, threaded=True, port=port)
    logger.info(f'API v1.0 online: http://{host}:{port}')
    # print("I'm here")
