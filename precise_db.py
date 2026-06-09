"""
precise_db.py — Token-gated fast DuckDB access for PALSlab Hub notebooks.

Uses Apache Arrow IPC transport — binary format, no JSON overhead.
The DuckDB file is chmod 600 (rutendo only); this is the only valid access path.

Usage:
    import sys
    sys.path.insert(0, '/home/rutendo/PRECISE')
    from precise_db import PreciseDB

    with PreciseDB(api_key="pals_xxx") as db:
        df = db.query("SELECT * FROM daily_data")
        df = db.query("SELECT Country, COUNT(*) n FROM daily_data GROUP BY Country")
"""
import io
import requests as _requests
import pyarrow.ipc as _ipc

_API_BASE = 'http://localhost:5000'


class PreciseDB:
    """
    Token-gated connection to the PRECISE dataset.

    - Queries use Arrow IPC binary format — fast even for millions of rows.
    - Country filter is enforced server-side — cannot be bypassed.
    - The underlying DuckDB file is chmod 600; direct access is blocked at OS level.
    """

    def __init__(self, api_key: str):
        self._key     = api_key
        self._session = _requests.Session()
        self._session.headers.update({'X-API-Key': api_key})

        r = self._session.get(f'{_API_BASE}/api/health')
        if r.status_code == 401:
            raise PermissionError(
                'No API key. Request access at:\n'
                'https://placealert.org/duckrequest/request'
            )
        if r.status_code == 403:
            raise PermissionError(
                'Invalid or revoked API key.\n'
                'Contact the admin or re-apply at:\n'
                'https://placealert.org/duckrequest/request'
            )
        r.raise_for_status()
        info = r.json()
        self._countries = info['authorised_countries']
        self._name      = info['user']
        self.summary()

    # ── Public API ────────────────────────────────────────────────────────────

    def query(self, sql: str, max_rows: int = None) -> 'pandas.DataFrame':
        """
        Run a SELECT query. Returns a pandas DataFrame in original column order.
        Uses Arrow binary transport — efficient for millions of rows.

        Parameters
        ----------
        sql      : SQL query (SELECT only)
        max_rows : optional hard limit on rows returned
        """
        payload = {'sql': sql}
        if max_rows is not None:
            payload['max_rows'] = int(max_rows)

        r = self._session.post(f'{_API_BASE}/api/query/arrow', json=payload)

        if r.status_code == 403:
            raise PermissionError('API key revoked. Contact the admin.')
        if r.status_code == 400:
            # Error comes back as JSON even from Arrow endpoint
            try:
                msg = r.json().get('error', 'Bad query')
            except Exception:
                msg = r.text
            raise ValueError(msg)
        r.raise_for_status()

        reader = _ipc.open_stream(io.BytesIO(r.content))
        return reader.read_pandas()

    # ── Exploratory helpers ───────────────────────────────────────────────────

    def columns(self) -> list:
        """Return list of column names in daily_data."""
        r = self._session.post(f'{_API_BASE}/api/query', json={'sql': 'DESCRIBE daily_data'})
        r.raise_for_status()
        data = r.json()
        return [row[0] for row in data['rows']]

    def shape(self) -> tuple:
        """Return (n_rows, n_cols) for daily_data (your approved countries only)."""
        r = self._session.post(f'{_API_BASE}/api/query',
                               json={'sql': 'SELECT COUNT(*) FROM daily_data'})
        r.raise_for_status()
        n_rows = r.json()['rows'][0][0]
        n_cols = len(self.columns())
        return (n_rows, n_cols)

    def head(self, n: int = 5) -> 'pandas.DataFrame':
        """Return first n rows as a DataFrame."""
        return self.query(f'SELECT * FROM daily_data LIMIT {int(n)}')

    def dtypes(self) -> 'pandas.DataFrame':
        """Return column names and their DuckDB types."""
        r = self._session.post(f'{_API_BASE}/api/query', json={'sql': 'DESCRIBE daily_data'})
        r.raise_for_status()
        data = r.json()
        import pandas as _pd
        return _pd.DataFrame(data['rows'], columns=data['columns'])[['column_name', 'column_type']]

    def summary(self):
        """Print a quick overview: shape, approved countries, first few columns."""
        n_rows, n_cols = self.shape()
        cols = self.columns()
        print(f"User      : {self._name}")
        print(f"Countries : {', '.join(self._countries)}")
        print(f"Shape     : {n_rows:,} rows × {n_cols} columns")
        print(f"Columns   : {', '.join(cols[:8])}{'...' if len(cols) > 8 else ''}")

    @property
    def countries(self):
        """Countries this key is approved to access."""
        return list(self._countries)

    def info(self):
        """Print permission summary."""
        print(f"User      : {self._name}")
        print(f"Countries : {', '.join(self._countries)}")

    def close(self):
        self._session.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def __repr__(self):
        return f"PreciseDB(user={self._name!r}, countries={self._countries})"
