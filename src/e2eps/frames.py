"""Time and reference-frame utilities (vectorised).

Frames
------
ECI  : Earth-centred inertial (simplified: no precession/nutation).
ECEF : Earth-centred Earth-fixed, obtained from ECI by rotating about Z by GMST.
Geodetic : WGS84 latitude/longitude/altitude.

Simplification: ignoring precession/nutation/polar motion gives sub-km errors,
acceptable for coverage/visibility studies (documented assumption).
"""
from __future__ import annotations

from datetime import datetime, timezone

import numpy as np

# WGS84 / Earth constants
MU_EARTH = 3.986004418e14       # m^3/s^2
R_EARTH = 6378137.0             # m, equatorial radius (WGS84 a)
F_WGS84 = 1 / 298.257223563     # flattening
E2_WGS84 = F_WGS84 * (2 - F_WGS84)
J2 = 1.08262668e-3
OMEGA_EARTH = 7.2921150e-5      # rad/s
C_LIGHT = 299_792_458.0         # m/s


def julian_date(dt: datetime) -> float:
    """Julian date of a timezone-aware UTC datetime."""
    dt = dt.astimezone(timezone.utc)
    j2000 = datetime(2000, 1, 1, 12, tzinfo=timezone.utc)
    return 2451545.0 + (dt - j2000).total_seconds() / 86400.0


def gmst_rad(epoch: datetime, t_s: np.ndarray) -> np.ndarray:
    """Greenwich mean sidereal angle [rad] at epoch + t_s seconds (IAU 1982 linear form)."""
    jd = julian_date(epoch) + np.asarray(t_s, dtype=float) / 86400.0
    deg = 280.46061837 + 360.98564736629 * (jd - 2451545.0)
    return np.deg2rad(np.mod(deg, 360.0))


def eci_to_ecef(r_eci: np.ndarray, gmst: np.ndarray) -> np.ndarray:
    """Rotate positions [T, N, 3] from ECI to ECEF given GMST angles [T]."""
    c, s = np.cos(gmst)[:, None], np.sin(gmst)[:, None]
    x, y, z = r_eci[..., 0], r_eci[..., 1], r_eci[..., 2]
    return np.stack((c * x + s * y, -s * x + c * y, z), axis=-1)


def geodetic_to_ecef(lat_deg, lon_deg, alt_m) -> np.ndarray:
    """WGS84 geodetic -> ECEF [.., 3] metres. Inputs broadcast."""
    lat, lon = np.deg2rad(lat_deg), np.deg2rad(lon_deg)
    alt = np.asarray(alt_m, dtype=float)
    n = R_EARTH / np.sqrt(1 - E2_WGS84 * np.sin(lat) ** 2)
    x = (n + alt) * np.cos(lat) * np.cos(lon)
    y = (n + alt) * np.cos(lat) * np.sin(lon)
    z = (n * (1 - E2_WGS84) + alt) * np.sin(lat)
    return np.stack((x, y, z), axis=-1)


def enu_rotation(lat_deg, lon_deg) -> np.ndarray:
    """Rotation matrices [G, 3, 3] mapping ECEF vectors to local East-North-Up."""
    lat, lon = np.deg2rad(np.atleast_1d(lat_deg)), np.deg2rad(np.atleast_1d(lon_deg))
    sl, cl, so, co = np.sin(lat), np.cos(lat), np.sin(lon), np.cos(lon)
    zero = np.zeros_like(lat)
    return np.stack((
        np.stack((-so, co, zero), axis=-1),
        np.stack((-sl * co, -sl * so, cl), axis=-1),
        np.stack((cl * co, cl * so, sl), axis=-1),
    ), axis=-2)
