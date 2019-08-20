#!/usr/bin/env python
import pyglet
from pyglet.window import key
import numpy as np

from pyglet_gui.theme import Theme
from pyglet_gui.buttons import Button
from pyglet_gui.manager import Manager
from pyglet_gui.containers import VerticalContainer

theme = Theme({"font": "Lucida Grande",
               "font_size": 12,
               "text_color": [255, 255, 255, 255],
               "gui_color": [255, 0, 0, 255],
               "button": {
                   "down": {
                       "image": {
                           "source": "button-down.png",
                           "frame": [8, 6, 2, 2],
                           "padding": [18, 18, 8, 6]
                       },
                       "text_color": [0, 0, 0, 255]
                   },
                   "up": {
                       "image": {
                           "source": "button.png",
                           "frame": [6, 5, 6, 3],
                           "padding": [18, 18, 8, 6]
                       }
                   }
               }
              }, resources_path='')

PI_180 = np.pi/180
np.random.seed(0)

#
# Parameters that control game behavior and difficulty
#

ast_sizes = [1, 1/2, 1/4]  # Factor by which asteroids shrink as they break
ast_points = [100, 50, 25] # How many points each asteroid is worth
p_acc = 100                # Acceleration of player's ship
p_rot_rate = 10.0          # Rotation rate of player's ship
shoot_speed = 600          # Speed of bullets
ast_max_vel = 50           # Max of x and y components of velocity of asteroids
ast_break_max_vel = 50     # Max amount to add to asteroid vel components after break
num_ast = 10               # Initial number of asteroids to generate
lives = 2                  # Number of etra lives that player stars with

window = pyglet.window.Window(800, 600)

def make_img(filename, anchor_x=None, anchor_y=None):
	img = pyglet.image.load(filename)
	img.anchor_x = img.width // 2
	img.anchor_y = img.height // 2
	if anchor_x is not None:
		img.anchor_x = anchor_x
	if anchor_y is not None:
		img.anchor_y = anchor_y
	return img

def ang_to_vec(angle):
	a_norm_x = np.cos(angle*PI_180)
	a_norm_y = -np.sin(angle*PI_180)
	return a_norm_x, a_norm_y

def wrap(xpos, ypos, xmin, xmax, ymin, ymax):
	if xpos < xmin:
		xpos = xmax
	if xpos > xmax:
		xpos = xmin
	if ypos < ymin:
		ypos = ymax
	if ypos > ymax:
		ypos = ymin

	return xpos, ypos

def off_screen(xpos, ypos, xmin, xmax, ymin, ymax):
	newx, newy = wrap(xpos, ypos, xmin, xmax, ymin, ymax)
	if (newx != xpos) or (newy != ypos):
		return True
	return False

class Bullet:
	def __init__(self, game, xpos, ypos, xvel, yvel):
		self.xpos = xpos
		self.ypos = ypos
		self.xvel = xvel
		self.yvel = yvel
		self.game = game

		bullet_img = make_img('bullet.png')
		self.bullet = pyglet.sprite.Sprite(bullet_img, x=self.xpos, y=self.ypos, batch=game.batch)

	# Return True if the bullet went off the screen and needs to be deleted
	def update(self, dt):
		self.xpos += self.xvel*dt
		self.ypos += self.yvel*dt

		return off_screen(self.xpos, self.ypos, self.game.xmin, self.game.xmax,
			              self.game.ymin, self.game.ymax)

class Asteroid:
	def __init__(self, game, xpos, ypos, xvel, yvel, size):
		self.xpos = xpos
		self.ypos = ypos
		self.xvel = xvel
		self.yvel = yvel
		self.size = size
		self.rot = np.random.rand()*360
		self.exploding = False
		self.game = game

		asteroid_img = make_img('asteroid.png')
		self.asteroid = pyglet.sprite.Sprite(asteroid_img, x=self.xpos, y=self.ypos,
			                                 batch=game.batch, group=game.background)

	def update(self, dt):
		self.xpos += self.xvel*dt
		self.ypos += self.yvel*dt

		self.xpos, self.ypos = wrap(self.xpos, self.ypos, self.game.xmin,
			                        self.game.xmax, self.game.ymin, 
			                        self.game.ymax)

class Game:
	def __init__(self, window):
		self.window = window
		self.background = pyglet.graphics.OrderedGroup(0)
		self.foreground = pyglet.graphics.OrderedGroup(1)
		self.xmin, self.xmax = 0, self.window.width
		self.ymin, self.ymax = 0, self.window.height
		self.state = 'MENU'
		self.player_img = make_img('player.png')
		self.init_menu_state()

	def gen_exp_anim(self):
		exp_anim = pyglet.image.Animation.from_image_sequence(self.explosion_seq, 0.1, False)
		return exp_anim

	def init_menu_state(self):
		self.batch = pyglet.graphics.Batch()

		label = pyglet.text.Label('AsTeRoIdS', font_name='Times New Roman',
                                  font_size=36,  x=window.width//2,
                                  y=3*window.height//4, anchor_x='center',
                                  anchor_y='center', batch=self.batch, group=self.foreground)

		def callback1(is_pressed):
			self.init_game_state()
			self.state = 'PLAYING'
		button1 = Button('Start Game', on_press=callback1)

		def callback2(is_pressed):
			exit()
		button2 = Button('Quit', on_press=callback2)
		Manager(VerticalContainer([button1, button2]), window=window,
			    theme=theme, batch=self.batch)

		self.asteroids = self.gen_asteroids(num_ast)

	def init_game_state(self):
		self.batch = pyglet.graphics.Batch()

		self.reset()

		self.shoot_start = self.player.width // 2
		flame_img = make_img('flame.png', anchor_x=55)
		self.flame = pyglet.sprite.Sprite(flame_img, x=self.p_xpos, y=self.p_ypos, group=self.background)

		explosion = pyglet.image.load('explosion.png')
		self.explosion_seq = pyglet.image.ImageGrid(explosion, 1, 7)

		s_fac = 0.5
		self.s_lives = []
		live_img = make_img('player.png')
		for i in range(lives):
			live_sprite = pyglet.sprite.Sprite(live_img, x=0, y=0, batch=self.batch,
				                               group=self.foreground)
			xpos = i*(live_sprite.width*s_fac) + live_sprite.width // 2
			ypos = self.ymax - live_sprite.height // 2
			live_sprite.update(xpos, ypos, scale=s_fac, rotation=-90)
			self.s_lives.append(live_sprite)

		self.score = 0
		self.score_prefix = 'Score: '
		self.score_label = pyglet.text.Label('', font_name='Times New Roman',
                                            font_size=18, batch=self.batch,
                                            anchor_x='left', anchor_y='center',
                                            group=self.foreground)
		self.score_label.x = live_sprite.width*(lives+1)
		self.score_label.y = live_sprite.y
		self.update_score_ui()

		self.key_left = False
		self.key_right = False
		self.key_up = False
		self.key_space = False

	def init_dead_state(self):
		self.score_label.delete()
		
		gameover_label = pyglet.text.Label('Game Over', font_name='Times New Roman',
                                           font_size=36,  x=window.width//2,
                                           y=3*window.height//4, anchor_x='center',
                                           anchor_y='center', batch=self.batch)

		text = 'Final Score: ' + str(self.score)
		finalscore_label = pyglet.text.Label(text, font_name='Times New Roman',
                                           font_size=18,  x=window.width//2,
                                           y=3*window.height//4-50, anchor_x='center',
                                           anchor_y='center', batch=self.batch)

		def callback1(is_pressed):
			self.init_game_state()
			self.state = 'PLAYING'
		button1 = Button('Start Game', on_press=callback1)

		def callback2(is_pressed):
			exit()
		button2 = Button('Quit', on_press=callback2)
		Manager(VerticalContainer([button1, button2]), window=window,
			    theme=theme, batch=self.batch)

	def done_exploding_player(self):
		if len(self.s_lives) == 0:
			self.init_dead_state()
			self.state = 'DEAD'
		else:
			self.s_lives.remove(self.s_lives[-1])
			self.reset()

	def reset(self):
		self.p_xpos = (self.xmax - self.xmin)/2
		self.p_ypos = (self.ymax - self.ymin)/2
		self.p_xvel, self.p_yvel = 0, 0
		self.p_rot = 0
		self.player = pyglet.sprite.Sprite(self.player_img, x=self.p_xpos, y=self.p_ypos, batch=game.batch)
		self.exploded = False
		self.bullets = []
		self.asteroids = self.gen_asteroids(num_ast)

	def update_score_ui(self):
		score_str = self.score_prefix + '{:4d}'.format(self.score)
		self.score_label.text = score_str

	def gen_asteroids(self, N):
		asteroids = []
		xpos = np.random.rand(N)*self.xmax
		ypos = np.random.rand(N)*self.ymax
		xvel = np.random.rand(N)*ast_max_vel*2 - ast_max_vel
		yvel = np.random.rand(N)*ast_max_vel*2 - ast_max_vel
		size_inds = np.asarray(np.random.rand(N)*len(ast_sizes), dtype=int)
		sizes = []
		for i, idx in enumerate(size_inds):
			sizes.append(ast_sizes[idx])

		for i in range(N):
			ast = Asteroid(self, xpos[i], ypos[i], xvel[i], yvel[i], sizes[i])
			asteroids.append(ast)

		return asteroids

	# Check every bullet and asteroid pair for a collision and return
	# the indices of both in the list if a collision occurs
	def check_bullet_ast_coll(self):
		for idx1 in range(len(self.bullets)):
			for idx2 in range(len(self.asteroids)):
				if self.asteroids[idx2].exploding:
					continue
				x1 = self.bullets[idx1].xpos
				x2 = self.asteroids[idx2].xpos
				y1 = self.bullets[idx1].ypos
				y2 = self.asteroids[idx2].ypos
				radius = self.asteroids[idx2].asteroid.width // 2

				dist = np.sqrt((x1 - x2)**2 + (y1 - y2)**2)

				if dist <= radius:
					return idx1, idx2

		return -1, -1

	# Check for a collision between the player and every asteroid
	# and return the index of the asteroid if one occurs
	def check_player_ast_coll(self):
		for idx in range(len(self.asteroids)):
			if self.asteroids[idx].exploding:
					continue
			x1 = self.p_xpos
			x2 = self.asteroids[idx].xpos
			y1 = self.p_ypos
			y2 = self.asteroids[idx].ypos
			radius = self.player.width // 2

			dist = np.sqrt((x1 - x2)**2 + (y1 - y2)**2)

			if dist <= radius:
				return idx

		return -1

	def shoot(self):
		a_norm_x, a_norm_y = ang_to_vec(self.p_rot)
		b_xpos = a_norm_x*self.shoot_start
		b_ypos = a_norm_y*self.shoot_start
		b_xvel = a_norm_x*shoot_speed
		b_yvel = a_norm_y*shoot_speed
		b = Bullet(self, self.p_xpos + b_xpos, self.p_ypos + b_ypos,
			       self.p_xvel + b_xvel, self.p_yvel + b_yvel)
		self.bullets.append(b)

	# Break an asteroid into smaller pieces
	def break_asteroid(self, idx):
		a = self.asteroids[idx]
		self.asteroids[idx].asteroid.image = self.gen_exp_anim()
		self.asteroids[idx].exploding = True
		def asteroid_done():
			self.asteroids.remove(a)
		self.asteroids[idx].asteroid.on_animation_end = asteroid_done

		if a.size == ast_sizes[-1]:
			return
		
		size_idx = ast_sizes.index(a.size)
		xv_add = np.random.rand(2)*ast_break_max_vel*2 - ast_break_max_vel
		yv_add = np.random.rand(2)*ast_break_max_vel*2 - ast_break_max_vel
		a1_new = Asteroid(self, a.xpos, a.ypos, a.xvel + xv_add[0],
			              a.yvel + yv_add[0], ast_sizes[size_idx+1])
		a2_new = Asteroid(self, a.xpos, a.ypos, a.xvel + xv_add[1],
			              a.yvel + yv_add[1], ast_sizes[size_idx+1])

		self.asteroids.append(a1_new)
		self.asteroids.append(a2_new)

	def update(self, dt):
		if self.state == 'MENU':
			self.menu_update(dt)
		elif self.state == 'PLAYING':
			self.playing_update(dt)

	def menu_update(self, dt):
		for a in self.asteroids:
			a.update(dt)

	def playing_update(self, dt):
		# Update player position
		if not self.exploded:
			self.p_xpos, self.p_ypos = wrap(self.p_xpos, self.p_ypos, self.xmin,
				                            self.xmax, self.ymin, self.ymax)

			self.p_xpos += self.p_xvel*dt
			self.p_ypos += self.p_yvel*dt

		# Update asteroid and bullet positions
		for a in self.asteroids:
			a.update(dt)

		for b in self.bullets:
			cleanup = b.update(dt)
			if cleanup:
				self.bullets.remove(b)

		# Check for player-asteroid and bullet-asteroid collisions
		if not self.exploded:
			i1 = self.check_player_ast_coll()
			if i1 >= 0:
				self.exploded = True
				self.release_all_keys()
				self.player.image = self.gen_exp_anim()
				self.player.on_animation_end = self.done_exploding_player

		i1, i2 = self.check_bullet_ast_coll()
		if i1 >= 0 and i2 >= 0:
			self.bullets.remove(self.bullets[i1])
			points = ast_points[ast_sizes.index(self.asteroids[i2].size)]
			self.score += points
			self.break_asteroid(i2)

		self.update_score_ui()

		# Handle keyboard input
		if self.key_left:
			self.p_rot -= p_rot_rate
			if self.p_rot < 0:
				self.p_rot += 360
		if self.key_right:
			self.p_rot += p_rot_rate
			if self.p_rot > 360:
				self.p_rot -= 360
		if self.key_up:
			a_norm_x, a_norm_y = ang_to_vec(self.p_rot)
			self.p_xvel += a_norm_x*p_acc*dt
			self.p_yvel += a_norm_y*p_acc*dt
		if self.key_space:
			self.shoot()
			self.key_space = False # Prevent player from holding down the shoot button

	def release_all_keys(self):
		self.key_space = False
		self.key_up = False
		self.key_left = False
		self.key_right = False

game = Game(window)

@window.event
def on_key_press(symbol, modifiers):
	if game.state == 'PLAYING':
		if game.exploded:
			return

		if symbol == key.LEFT:
			game.key_left = True
		if symbol == key.RIGHT:
			game.key_right = True
		if symbol == key.UP:
			game.key_up = True
		if symbol == key.SPACE:
			game.key_space = True

@window.event
def on_key_release(symbol, modifiers):
	if game.state == 'PLAYING':
		if game.exploded:
			return

		if symbol == key.LEFT:
			game.key_left = False
		if symbol == key.RIGHT:
			game.key_right = False
		if symbol == key.UP:
			game.key_up = False
		if symbol == key.SPACE:
			game.key_space = False

@window.event
def on_draw():
	window.clear()

	if game.state == 'MENU':
		for a in game.asteroids:
			a.asteroid.update(a.xpos, a.ypos, scale=a.size, rotation=a.rot)

		game.batch.draw()

	if game.state == 'PLAYING':
		for a in game.asteroids:
			a.asteroid.update(a.xpos, a.ypos, scale=a.size, rotation=a.rot)

		game.player.update(x=game.p_xpos, y=game.p_ypos, rotation=game.p_rot)

		for b in game.bullets:
			b.bullet.update(b.xpos, b.ypos)

		if game.key_up:
			game.flame.update(x=game.p_xpos, y=game.p_ypos,
				             rotation=game.p_rot)
			game.flame.draw()

		game.batch.draw()

	if game.state == 'DEAD':
		game.batch.draw()

if __name__ == "__main__":
	pyglet.clock.schedule_interval(game.update, 1 / 120.0)

	# Tell pyglet to do its thing
	pyglet.app.run()