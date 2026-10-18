#ifndef __RK_MACRO___VERSION_H
#define __RK_MACRO___VERSION_H

/* The single source of the version. Edit it with repokit-common's
 * sync-versions.py (--bump, --set, --phase, --pre-num); CMake, the .rc file
 * and the code read it. Only #define lines: the resource compiler includes
 * this file too.
 *   PHASE            per-MINOR feature-set maturity: "" (stable), "alpha", "beta", "rc1"
 *   PRE_RELEASE_NUM  the PEP 440 counter behind alpha/beta (a1, b2); the tool writes it
 *   PROJECT_PHASE    project-wide maturity: "" or "stable", "prealpha", "alpha", "beta";
 *                    edited by hand, shown by --version, never changed by the tool */
#define __RK_MACRO___VERSION_MAJOR 0
#define __RK_MACRO___VERSION_MINOR 1
#define __RK_MACRO___VERSION_PATCH 0
#define __RK_MACRO___VERSION_PHASE ""
#define __RK_MACRO___VERSION_PRE_RELEASE_NUM 1
#define __RK_MACRO___PROJECT_PHASE ""
#define __RK_MACRO___VERSION_STRING "0.1.0"

#endif
