"""Consultas por fecha local; importes exactos en centavos, sin límite de filas."""
from datetime import date


def sales_report(db, start='', end='', state='Todas'):
    for value in (start, end):
        if value:
            try:
                if date.fromisoformat(value).isoformat()!=value:
                    raise ValueError()
            except ValueError as ex:
                raise ValueError('Usá fechas AAAA-MM-DD') from ex
    if start and end and start>end:
        raise ValueError('La fecha desde debe ser anterior o igual a hasta')
    if state not in ('Todas','Registradas','Anuladas'):
        raise ValueError('Estado inválido')
    clauses=[]
    params=[]
    for value,op in ((start,'>='),(end,'<=')):
        if value:
            clauses.append("date(s.created_at,'localtime') "+op+' ?')
            params.append(value)
    if state!='Todas':
        clauses.append('r.sale IS '+('NOT ' if state=='Anuladas' else '')+'NULL')
    query="""SELECT s.receipt_number ticket,datetime(s.created_at,'localtime') fecha,
        COALESCE(k.name,'Consumidor final') cliente,s.total_cents,COALESCE(d.amount,0) discount_cents,
        s.payment_method medio,CASE WHEN r.sale IS NULL THEN 'Registrada' ELSE 'Anulada' END estado
        FROM sales s LEFT JOIN checkouts c ON c.sale=s.id
        LEFT JOIN customers k ON k.id=c.customer LEFT JOIN reversals r ON r.sale=s.id
        LEFT JOIN sale_discounts d ON d.sale=s.id"""
    rows=[dict(r) for r in db.execute(query+(' WHERE '+' AND '.join(clauses) if clauses else '')+' ORDER BY s.receipt_number DESC',params)]
    totals={key:sum(r['total_cents'] for r in rows if r['estado']==label)
            for key,label in (('confirmed','Registrada'),('cancelled','Anulada'))}
    return rows,totals
