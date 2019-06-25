#ifndef IO_H
#define IO_H

namespace io {
  class Terminal {
    Terminal(void);
    virtual ~Terminal(void);

    void write(const std::string &message);
    std::string read(const std::string &prompt);
  };
}

#endif
