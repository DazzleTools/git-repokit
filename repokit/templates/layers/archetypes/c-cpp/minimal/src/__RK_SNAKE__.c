/* __RK_PROJECT__ -- __RK_DESCRIPTION__ */
#include <ctype.h>
#include <stdio.h>
#include <string.h>

#include "__RK_SNAKE__/version.h"

/* Like Python's get_display_version(): "ALPHA 0.1.0" while the project-wide
 * phase is set, "0.1.0" once it is empty or "stable". */
static void print_project_phase(void) {
    const char *phase = __RK_MACRO___PROJECT_PHASE;
    if (phase[0] == '\0' || strcmp(phase, "stable") == 0) return;
    for (; *phase; ++phase) putchar(toupper((unsigned char)*phase));
    putchar(' ');
}

int main(int argc, char **argv) {
    if (argc > 1 && strcmp(argv[1], "--version") == 0) {
        printf("__RK_PROJECT__ ");
        print_project_phase();
        printf("%s\n", __RK_MACRO___VERSION_STRING);
        return 0;
    }
    printf("__RK_PROJECT__: try --version\n");
    return 0;
}
