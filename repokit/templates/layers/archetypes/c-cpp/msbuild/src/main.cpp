// __RK_PROJECT__ -- __RK_DESCRIPTION__
#include <cctype>
#include <cstdio>
#include <cstring>

#include "__RK_SNAKE__/version.h"

// Like Python's get_display_version(): "ALPHA 0.1.0" while the project-wide
// phase is set, "0.1.0" once it is empty or "stable".
static void print_project_phase() {
    const char* phase = __RK_MACRO___PROJECT_PHASE;
    if (phase[0] == '\0' || std::strcmp(phase, "stable") == 0) return;
    for (; *phase; ++phase) std::putchar(std::toupper(static_cast<unsigned char>(*phase)));
    std::putchar(' ');
}

int main(int argc, char** argv) {
    if (argc > 1 && std::strcmp(argv[1], "--version") == 0) {
        std::printf("__RK_PROJECT__ ");
        print_project_phase();
        std::printf("%s\n", __RK_MACRO___VERSION_STRING);
        return 0;
    }
    std::printf("__RK_PROJECT__: try --version\n");
    return 0;
}
