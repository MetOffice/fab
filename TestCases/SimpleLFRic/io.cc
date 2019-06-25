#include <iostream>

#include "io.h"

io::Terminal::Terminal(void) {
}

io::Terminal::~Terminal(void) {
}

void io::Terminal::write(const std::string &message) {
    std::cout << message << std::endl;
}

std::string io::Terminal::read(const std::string &prompt) {
    std::string response;

    std::cout << prompt << " > ";
    std::cin >> response;
    std::cout << std::endl;

    return response;
}
