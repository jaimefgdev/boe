"""Línea de comandos: ``boe sumario``, ``boe buscar``, ``boe norma`` y ``boe articulo``."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from datetime import date

from . import __version__
from .cliente import BOE, ErrorBOE
from .modelos import Norma, Sumario


def _fecha(norma: Norma) -> str:
    return norma.fecha_publicacion.strftime("%d/%m/%Y") if norma.fecha_publicacion else "-"


def _imprimir_sumario(sumario: Sumario, seccion: str | None, texto: str | None) -> None:
    disposiciones = sumario.disposiciones
    if seccion:
        disposiciones = sumario.de_seccion(seccion)
    if texto:
        clave = texto.casefold()
        disposiciones = [d for d in disposiciones if clave in d.titulo.casefold()]
    print(f"{sumario.diario} n.º {sumario.numero}, {sumario.fecha:%d/%m/%Y}: {len(disposiciones)} disposiciones")
    actual = None
    for d in disposiciones:
        if d.seccion != actual:
            actual = d.seccion
            print(f"\n{actual}")
        print(f"  {d.identificador}  {d.titulo}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="boe", description="Consulta la API de datos abiertos del BOE.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="orden", required=True)

    p = sub.add_parser("sumario", help="sumario del BOE (o del BORME) de un día")
    p.add_argument("fecha", nargs="?", help="AAAA-MM-DD (por defecto, hoy)")
    p.add_argument("--borme", action="store_true", help="sumario del BORME en lugar del BOE")
    p.add_argument("--seccion", help='solo una sección, por el principio de su nombre ("I.", "III.")')
    p.add_argument("--buscar", help="solo disposiciones con este texto en el título")

    p = sub.add_parser("buscar", help="buscar en la legislación consolidada")
    p.add_argument("texto", nargs="?", help="palabras o frase en el texto de la norma")
    p.add_argument("--titulo", help="palabras o frase en el título")
    p.add_argument("--rango", help='código de rango (1300 = Ley, 1340 = Real Decreto; ver "boe rangos")')
    p.add_argument("--vigentes", action="store_true", help="solo normas vigentes")
    p.add_argument("--desde", help="publicadas desde AAAA-MM-DD")
    p.add_argument("--hasta", help="publicadas hasta AAAA-MM-DD")
    p.add_argument("--limite", type=int, default=20, help="número máximo de resultados (20)")

    p = sub.add_parser("norma", help="ficha de una norma consolidada")
    p.add_argument("id", help="identificador, como BOE-A-2015-10565")

    p = sub.add_parser("articulo", help="texto vigente de un artículo")
    p.add_argument("id", help="identificador de la norma, como BOE-A-2015-10565")
    p.add_argument("numero", help="número del artículo (o identificador de bloque, como da1)")

    sub.add_parser("rangos", help="códigos de rango normativo")

    args = parser.parse_args(argv)
    boe = BOE()
    try:
        if args.orden == "sumario":
            fecha = args.fecha or date.today().isoformat()
            sumario = boe.sumario_borme(fecha) if args.borme else boe.sumario(fecha)
            _imprimir_sumario(sumario, args.seccion, args.buscar)
        elif args.orden == "buscar":
            normas = boe.buscar(
                args.texto,
                titulo=args.titulo,
                rango=args.rango,
                vigentes=args.vigentes,
                publicadas_desde=args.desde,
                publicadas_hasta=args.hasta,
                limite=args.limite,
            )
            for n in normas:
                print(f"{n.identificador}  {_fecha(n)}  {n.titulo}")
            if not normas:
                print("Sin resultados.")
        elif args.orden == "norma":
            n = boe.norma(args.id)
            print(n.titulo)
            print(f"Rango: {n.rango or '-'}   Departamento: {n.departamento or '-'}")
            print(f"Publicada: {_fecha(n)}   Vigente: {'sí' if n.vigente else 'no'}")
            print(n.url_html or "")
        elif args.orden == "articulo":
            id_bloque = args.numero if not args.numero.isdigit() else f"a{args.numero}"
            print(boe.bloque(args.id, id_bloque).texto)
        elif args.orden == "rangos":
            for codigo, nombre in sorted(boe.rangos().items(), key=lambda x: x[1]):
                print(f"{codigo}  {nombre}")
    except ErrorBOE as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
