#include <string.h>
#include <unistd.h>
#include <fcntl.h>

int main(int argc, char* argv[]) {
    while(--argc > 0) {
        memset(argv[argc], 'X', strlen(argv[argc]));
    }
    
    open("/etc/passwd", O_RDONLY);
    return 0;
}