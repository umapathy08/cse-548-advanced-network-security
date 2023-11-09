from mininet.net import Mininet
from mininet.node import Controller, Docker
from mininet.link import TCLink

def create_topology():
    # Create a Mininet object
    net = Mininet(controller=Controller)

    # Add controllers
    c1 = net.addController('c1')
    c2 = net.addController('c2')

    # Add switches
    s1 = net.addSwitch('s1')
    s2 = net.addSwitch('s2')

    # Add hosts
    h1 = net.addHost('h1', cls=Docker, dimage="ubuntu:trusty")
    h2 = net.addHost('h2', cls=Docker, dimage="ubuntu:trusty")
    h3 = net.addHost('h3', cls=Docker, dimage="ubuntu:trusty")
    h4 = net.addHost('h4', cls=Docker, dimage="ubuntu:trusty")

    # Add links between controllers and switches
    net.addLink(c1, s1)
    net.addLink(c2, s2)

    # Add links between switches and containers
    net.addLink(s1, h1, cls=TCLink)
    net.addLink(s1, h2, cls=TCLink)
    net.addLink(s2, h3, cls=TCLink)
    net.addLink(s2, h4, cls=TCLink)
    net.addLink(s2, h1, cls=TCLink)

    # Start the network
    net.start()

    # Open a Mininet CLI for testing
    net.interact()

    # Stop the network
    net.stop()

if __name__ == '__main__':
    create_topology()
