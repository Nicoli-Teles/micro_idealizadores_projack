from fastapi import FastAPI, HTTPException, Form, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import sqlite3
import bcrypt
import os
from database import criar_tabelas
from models import Idealizador, Habilidade

# =============================
# CONFIGURAÇÃO DO APP
# =============================
app = FastAPI(title="Cadastro de Idealizadores")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # libera para todos os domínios (pode restringir depois)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# cria as tabelas se não existirem
criar_tabelas()


# =============================
# ROTAS BÁSICAS
# =============================
@app.get("/")
def home():
    return {"mensagem": "API de Cadastro funcionando 🚀"}


# =============================
# CADASTRO
# =============================
@app.post("/cadastro")
def cadastrar(idealizador: Idealizador):
    conexao = sqlite3.connect("banco.db")
    cursor = conexao.cursor()

    # Criptografa a senha e converte para string
    senha_criptografada = bcrypt.hashpw(
        idealizador.senha.encode("utf-8"), bcrypt.gensalt()
    ).decode("utf-8")

    try:
        cursor.execute(
            """
            INSERT INTO idealizadores 
            (nome, telefone, email, senha, github, linkedin, funcao, pais, cidade, sobre_mim, icon)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                idealizador.nome,
                idealizador.telefone,
                idealizador.email,
                senha_criptografada,
                idealizador.github,
                idealizador.linkedin,
                idealizador.funcao,
                idealizador.pais,
                idealizador.cidade,
                idealizador.sobre_mim,
                idealizador.icon or "cat_icon.png",
            ),
        )
        conexao.commit()
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="E-mail já cadastrado.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao cadastrar: {e}")
    finally:
        conexao.close()

    return {"mensagem": "Idealizador cadastrado com sucesso!"}


# =============================
# LOGIN
# =============================
class Login(BaseModel):
    email: str
    senha: str


@app.post("/login")
def login(credenciais: Login):
    conexao = sqlite3.connect("banco.db")
    cursor = conexao.cursor()
    cursor.execute("SELECT id, senha, nome FROM idealizadores WHERE email = ?", (credenciais.email,))
    resultado = cursor.fetchone()
    conexao.close()

    if not resultado:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    id_usuario, senha_armazenada, nome = resultado
    try:
        if bcrypt.checkpw(credenciais.senha.encode("utf-8"), senha_armazenada.encode("utf-8")):
            return {"mensagem": f"Bem-vindo {nome}!", "id": id_usuario}
        else:
            raise HTTPException(status_code=401, detail="Senha incorreta")
    except Exception:
        raise HTTPException(status_code=500, detail="Erro ao verificar senha")


# =============================
# PERFIL (GET e PUT)
# =============================

@app.get("/perfil/{idealizador_id}")
def obter_perfil(idealizador_id: int):
    conexao = sqlite3.connect("banco.db")
    cursor = conexao.cursor()

    cursor.execute("""
        SELECT id, nome, telefone, email, github, linkedin, funcao, pais, cidade, sobre_mim, icon
        FROM idealizadores WHERE id = ?
    """, (idealizador_id,))
    resultado = cursor.fetchone()

    if not resultado:
        conexao.close()
        raise HTTPException(status_code=404, detail="Perfil não encontrado")

    perfil = {
        "id": resultado[0],
        "nome": resultado[1] or "",
        "telefone": resultado[2] or "",
        "email": resultado[3] or "",
        "github": resultado[4] or "",
        "linkedin": resultado[5] or "",
        "funcao": resultado[6] or "",
        "pais": resultado[7] or "",
        "cidade": resultado[8] or "",
        "sobre_mim": resultado[9] or "",
        "icon": resultado[10] or "cat_icon.png",
    }

    # Buscar habilidades
    cursor.execute("SELECT nome FROM habilidades WHERE idealizador_id = ?", (idealizador_id,))
    habilidades = [h[0] for h in cursor.fetchall()]

    conexao.close()
    perfil["habilidades"] = habilidades
    return perfil


@app.put("/perfil/{idealizador_id}")
async def atualizar_perfil(
    idealizador_id: int,
    nome: Optional[str] = Form(None),
    telefone: Optional[str] = Form(None),
    github: Optional[str] = Form(None),
    linkedin: Optional[str] = Form(None),
    funcao: Optional[str] = Form(None),
    pais: Optional[str] = Form(None),
    cidade: Optional[str] = Form(None),
    sobre_mim: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    icon: Optional[str] = Form(None)  # 🔹 alterado para string
):
    conexao = sqlite3.connect("banco.db")
    cursor = conexao.cursor()

    campos = []
    valores = []

    campos_texto = {
        "nome": nome,
        "telefone": telefone,
        "github": github,
        "linkedin": linkedin,
        "funcao": funcao,
        "pais": pais,
        "cidade": cidade,
        "sobre_mim": sobre_mim,
        "email": email,
        "icon": icon  # 🔹 agora tratado como string normal
    }

    for campo, valor in campos_texto.items():
        if valor:
            campos.append(f"{campo} = ?")
            valores.append(valor)

    if not campos:
        raise HTTPException(status_code=400, detail="Nenhum dado enviado para atualizar.")

    valores.append(idealizador_id)
    query = f"UPDATE idealizadores SET {', '.join(campos)} WHERE id = ?"

    try:
        cursor.execute(query, valores)
        conexao.commit()
    except Exception as e:
        conexao.rollback()
        raise HTTPException(status_code=500, detail=f"Erro ao atualizar perfil: {e}")
    finally:
        conexao.close()

    return {"mensagem": "Perfil atualizado com sucesso!"}




# =============================
# HABILIDADES
# =============================
@app.get("/habilidades/{idealizador_id}")
def listar_habilidades(idealizador_id: int):
    conexao = sqlite3.connect("banco.db")
    cursor = conexao.cursor()
    cursor.execute("SELECT nome FROM habilidades WHERE idealizador_id = ?", (idealizador_id,))
    habilidades = [linha[0] for linha in cursor.fetchall()]
    conexao.close()
    return {"habilidades": habilidades}


@app.post("/habilidades/{idealizador_id}")
def salvar_habilidades(idealizador_id: int, habilidades: list[str]):
    conexao = sqlite3.connect("banco.db")
    cursor = conexao.cursor()
    cursor.execute("DELETE FROM habilidades WHERE idealizador_id = ?", (idealizador_id,))
    for nome in habilidades:
        cursor.execute("INSERT INTO habilidades (idealizador_id, nome) VALUES (?, ?)", (idealizador_id, nome))
    conexao.commit()
    conexao.close()
    return {"mensagem": "Habilidades atualizadas com sucesso!"}


# =============================
# EXCLUIR PERFIL
# =============================
@app.delete("/perfil/{idealizador_id}")
def excluir_perfil(idealizador_id: int):
    conexao = sqlite3.connect("banco.db")
    cursor = conexao.cursor()
    cursor.execute("SELECT id FROM idealizadores WHERE id = ?", (idealizador_id,))
    if not cursor.fetchone():
        conexao.close()
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")

    try:
        cursor.execute("DELETE FROM habilidades WHERE idealizador_id = ?", (idealizador_id,))
        cursor.execute("DELETE FROM idealizadores WHERE id = ?", (idealizador_id,))
        conexao.commit()
    except Exception as e:
        conexao.rollback()
        raise HTTPException(status_code=500, detail=f"Erro ao excluir perfil: {e}")
    finally:
        conexao.close()

    return {"mensagem": "Perfil e habilidades excluídos com sucesso!"}
