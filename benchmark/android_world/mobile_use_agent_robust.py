"""MobileUse agent for AndroidWorld."""
import logging
import sys
import traceback
import types
import time
from PIL import Image
import numpy as np
from skimage.metrics import structural_similarity as ssim

from android_world.agents import base_agent
from android_world.env import interface
import mobile_use

logger = logging.getLogger(__name__)

REF_IMAGE = Image.open("ref_image.png")
def compare_image(img1: Image.Image, img2: Image.Image):
    img1 = img1.convert('L')
    img2 = img2.convert('L')
    img1 = np.array(img1)
    img2 = np.array(img2)
    ssim_value = ssim(img1, img2)
    return ssim_value

def calculate_black_rate(img: Image.Image, threshold: int = 10):
    img_l = img.convert('L')
    img_array = np.array(img_l)
    black_rate = np.sum(img_array < threshold) / img_array.size
    return black_rate

class MobileUse(base_agent.EnvironmentInteractingAgent):
  """"""
  def __init__(
          self, 
          env: interface.AsyncEnv,
          agent: mobile_use.Agent,
          name: str = "MobileUse",
      ):
    super().__init__(env, name)
    self.agent = agent
    self.agent.reset()

    self.error_count = 0

  def reset(self, go_home: bool = False) -> None:
    super().reset(go_home)
    self.env.hide_automation_ui()
    self.agent.reset()

    time.sleep(7)
    start_image = self.agent.env.get_state().pixels.copy()
    time.sleep(3)
    ssim_value = compare_image(start_image, REF_IMAGE)
    logger.info(f"SSIM value: {ssim_value}")

    if ssim_value < 0.95:
      logger.warning("NOTICE!!! The start image is not similar to the reference image.")
      start_image.save(rf"D:\Users\S9057346\android_world\error_img\{ssim_value}.png")
      self.error_count += 1
      if self.error_count > 3:
          logger.warning("ERROR!!! Find 3 times error. Will exit.")
          exit()
      raise Exception("The start image is not similar to the reference image.")

  def step(self, goal: str) -> base_agent.AgentInteractionResult:
    if self.agent.goal != goal:
      self.agent.reset(goal=goal)
      logger.info("Start task: %s" % (self.agent.goal.encode("gbk", errors="replace").decode("gbk", errors="replace")))
      sys.stdout.flush()

    trajectory = self.agent.episode_data.trajectory
    if len(trajectory) > 0:
      pixel = trajectory[-1].curr_env_state.pixels
      black_rate_value = calculate_black_rate(pixel)
      if black_rate_value > 0.95:
        logger.warning(f"BLACK RATE: {black_rate_value}.")
        raise Exception("BLACK: The screen black rate is too high.")
      elif black_rate_value > 0.8:
        logger.warning(f"BLACK RATE: {black_rate_value}.")
        logger.warning("The screen black rate is high.")

    answer = None
    try:
      answer = self.agent.step()
      if isinstance(answer, types.GeneratorType):
        for _ in answer:
          pass
        answer = None
    except Exception as e:
      logger.info("Some error happened during the MobileUse agent run.")
      traceback.print_exc()
      self.agent.status = mobile_use.AgentStatus.FAILED
      self.agent.episode_data.status = self.agent.status
      self.agent.episode_data.message = str(e)
      return base_agent.AgentInteractionResult(True, {"step_data": self.agent.trajectory[-1]})

    self.agent.episode_data.num_steps = self.agent.curr_step_idx + 1
    self.agent.episode_data.status = self.agent.status

    if answer is not None:
       logger.info("Agent interaction cache is updated: %s" % answer)
       self.env.interaction_cache = answer

    ret_info = {"step_data": self.agent.trajectory[-1]}
    if len(self.agent.trajectory) == 1:
      if hasattr(self.agent.episode_data, 'input_tips') and self.agent.episode_data.input_tips:
        ret_info['input_tips'] = self.agent.episode_data.input_tips
      if hasattr(self.agent.episode_data, 'output_tips') and self.agent.episode_data.output_tips:
        ret_info['output_tips'] = self.agent.episode_data.output_tips
      if hasattr(self.agent.episode_data, 'retrieved_tips') and self.agent.episode_data.retrieved_tips:
        ret_info['retrieved_tips'] = self.agent.episode_data.retrieved_tips

    if self.agent.status == mobile_use.AgentStatus.FINISHED:
        logger.info("Agent indicates task is done.")
        self.agent.episode_data.message = 'Agent indicates task is done.'
        return base_agent.AgentInteractionResult(True, ret_info)
    elif self.agent.state == mobile_use.AgentState.CALLUSER:
        logger.warning("CALLUSER is not supported in AdroidWorld evaluation.")
        return base_agent.AgentInteractionResult(True, ret_info)
    else:
        self.agent.curr_step_idx += 1
        logger.info("Agent indicates one step is done.")
        return base_agent.AgentInteractionResult(False, ret_info)
